# -*- coding: utf-8 -*-

from odoo import api, models, fields
from dateutil.relativedelta import relativedelta


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    puntos_a_vencer_este_mes = fields.Float(
        string="A vencer este mes",
        readonly=True,
        help="Puntos próximos a caducar (FIFO: impago + vigencia del programa). "
             "Se recalcula automáticamente al sincronizar el historial.",
    )

    def _iter_fifo_available(self, dias_gracia):
        """
        Retorna una lista materializada de tuplas para emisiones que aún tienen
        saldo disponible según lógica FIFO.
        Tupla: (linea, disponible, fecha_limite_pago, fecha_limite_vigencia)
        """
        self.ensure_one()
        resultado = []

        # 1. Consumo global: usos + reversiones NC
        # (Las anulaciones (out_invoice) generan is_reversal pero no consumen saldo vivo, 
        # sino que netean ya en ya en already_issued)
        usos = sum(self.history_ids.mapped('used'))
        reversiones_nc = sum(
            abs(l.issued) for l in self.history_ids 
            if l.issued < 0 and l.is_reversal and l.invoice_id and l.invoice_id.move_type == 'out_refund'
        )
        total_consumido = usos + reversiones_nc

        validez_meses = self.program_id.validez_puntos_meses

        # 2. Emisiones vivas
        emisiones = self.history_ids.filtered(
            lambda l: l.issued > 0 
            and l.invoice_id and l.invoice_id.state == 'posted'
            and not l.is_reversal
            and not l.is_reversed
        ).sorted('f_creacion_factura')

        for linea in emisiones:
            disponible = linea.issued - linea.vencidos

            # Aplicar consumo FIFO
            if total_consumido > 0:
                consumir = min(total_consumido, disponible)
                total_consumido -= consumir
                disponible -= consumir

            if disponible <= 0:
                continue

            # Fechas límite
            fecha_limite_pago = False
            if linea.f_vencimiento_factura:
                fecha_limite_pago = linea.f_vencimiento_factura + relativedelta(days=dias_gracia)

            fecha_limite_vigencia = False
            if validez_meses > 0 and linea.f_creacion_factura:
                fecha_limite_vigencia = linea.f_creacion_factura + relativedelta(months=validez_meses)

            resultado.append((linea, disponible, fecha_limite_pago, fecha_limite_vigencia))

        return resultado

    def _calculate_expiring_points(self, dias_gracia):
        """
        Calcula cuántos puntos expiran en el mes actual SÓLO por tiempo de vigencia (ej. 6 meses).
        La lógica de riesgo por impago (5 días) se calcula separada para futuro uso (comentado).
        """
        self.ensure_one()
        hoy = fields.Date.today()
        inicio_mes = hoy.replace(day=1)
        fin_mes = inicio_mes + relativedelta(months=1, days=-1)
        
        puntos_a_vencer = 0.0
        puntos_en_riesgo = 0.0 # Guardado en variable pero no se usa en UI por ahora
        fifo_disponibles = self._iter_fifo_available(dias_gracia)

        for linea, disponible, f_pago, f_vigencia in fifo_disponibles:
            # Regla B: Vigencia caduca este mes (Los 6 meses)
            if f_vigencia:
                if inicio_mes <= f_vigencia <= fin_mes:
                    puntos_a_vencer += disponible
                    continue # Si ya está por vencer por tiempo, pasamos al siguiente
            
            # Regla A: Factura impaga y sus días de gracia se cumplen este mes (Riesgo de cancelación)
            if linea.invoice_id.payment_state in ['not_paid', 'partial'] and f_pago:
                if inicio_mes <= f_pago <= fin_mes:
                    puntos_en_riesgo += disponible

        # Por ahora solo retornamos los que vencen por tiempo (Regla B)
        # return puntos_a_vencer, puntos_en_riesgo
        return puntos_a_vencer

    def _sync_points_from_history(self):
        """
        Actualiza el saldo contable 'points' y la proyección 'puntos_a_vencer_este_mes'.
        """
        IrConfig = self.env['ir.config_parameter'].sudo()
        dias_gracia = int(IrConfig.get_param('pgm_osaka_loyalty.dias_vencimiento_factura', default=5))

        for card in self:
            if card.program_id.osaka_program_type not in ['puntos', 'amigos']:
                continue
            
            # El saldo contable usa TODAS las líneas (incluyendo reversiones y emisiones revertidas)
            # porque matemáticamente is_reversal e is_reversed se netean con sus originales
            # gracias a los creates/writes en account_move.
            issued = sum(card.history_ids.mapped('issued'))
            used = sum(card.history_ids.mapped('used'))
            vencidos = sum(card.history_ids.mapped('vencidos'))
            
            card.with_context(tracking_disable=True).write({
                'points': issued - used - vencidos,
                'puntos_a_vencer_este_mes': card._calculate_expiring_points(dias_gracia),
            })

    def _cron_expire_osaka_points(self):
        """
        Cron Diario: Expira puntos vencidos según Regla A (impago) y Regla B (vigencia).
        """
        hoy = fields.Date.today()
        osaka_cards = self.search([
            ('program_id.osaka_program_type', 'in', ['puntos', 'amigos']),
            ('history_ids', '!=', False)
        ])

        IrConfig = self.env['ir.config_parameter'].sudo()
        dias_gracia = int(IrConfig.get_param('pgm_osaka_loyalty.dias_vencimiento_factura', default=5))

        for card in osaka_cards:
            fifo_disponibles = card._iter_fifo_available(dias_gracia)

            for linea, disponible, f_pago, f_vigencia in fifo_disponibles:
                vence_por_impago = False
                if linea.invoice_id.payment_state in ['not_paid', 'partial'] and f_pago:
                    if hoy > f_pago:
                        vence_por_impago = True

                vence_por_vigencia = False
                if f_vigencia:
                    if hoy > f_vigencia:
                        vence_por_vigencia = True

                if vence_por_impago or vence_por_vigencia:
                    # Escribir 'vencidos' SÍ dispara el sync global por tarjeta (en write de history)
                    linea.write({
                        'vencidos': linea.vencidos + disponible,
                        'f_vencimiento_puntos': hoy
                    })

        # Refresco global al final para actualizar balances y "a vencer este mes"
        osaka_cards._sync_points_from_history()

    def action_recalculate_points_osaka(self):
        """
        Botón manual para forzar el recálculo de puntos a vencer y balance.
        """
        self._sync_points_from_history()

    def _cron_monthly_notification(self):
        """
        Cron Mensual (Día 1): Calcula puntos a vencer EN ESTE MES y envía 
        correos consolidados por commercial_partner_id (anti-spam).
        """
        osaka_cards = self.search([
            ('program_id.osaka_program_type', 'in', ['puntos', 'amigos']),
            ('history_ids', '!=', False)
        ])

        # 1. Sync global para tener datos frescos
        osaka_cards._sync_points_from_history()

        template = self.env.ref('pgm_osaka_loyalty.mail_template_osaka_partner_monthly', raise_if_not_found=False)
        if not template:
            return

        # 2. Agrupar por comercial
        partners = osaka_cards.mapped('partner_id.commercial_partner_id').filtered(lambda p: p.email)

        for partner in partners:
            partner_cards = osaka_cards.filtered(
                lambda c: c.partner_id.commercial_partner_id == partner
            )
            # 3. Guard Anti-Spam: Solo enviar si hay saldo o puntos por vencer
            if any(c.points > 0 or c.puntos_a_vencer_este_mes > 0 for c in partner_cards):
                template.send_mail(partner.id, force_send=True)
