# -*- coding: utf-8 -*-

import logging
from odoo import models, api, fields

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Foto del resumen al validar; no se recalcula en vivo tras el post.
    osaka_loyalty_summary_snapshot = fields.Json(
        string="Snapshot Lealtad Osaka",
        copy=False,
        readonly=True,
    )

    osaka_loyalty_summary_html = fields.Html(
        string="Resumen Puntos Osaka",
        compute="_compute_osaka_loyalty_summary",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Helpers — flete nunca aporta puntos (criterio Ana)
    # -------------------------------------------------------------------------
    def _osaka_so_product_total(self, sale_order):
        """Total de líneas de la SO que no son envío (is_delivery)."""
        lines = sale_order.order_line.filtered(
            lambda line: not line.display_type
            and not getattr(line, 'is_delivery', False)
        )
        return abs(sum(lines.mapped('price_total')))

    def _osaka_invoice_product_total(self, move, sale_order):
        """
        Total de esta factura atribuible a líneas de producto (no flete)
        de la SO indicada.
        """
        total = 0.0
        for inv_line in move.invoice_line_ids:
            sale_lines = inv_line.sale_line_ids.filtered(
                lambda sl: sl.order_id == sale_order and not sl.display_type
            )
            if not sale_lines:
                continue
            # Si todas las líneas SO ligadas son delivery → no suma a la base
            if all(getattr(sl, 'is_delivery', False) for sl in sale_lines):
                continue
            total += abs(inv_line.price_total)
        return total

    def _osaka_invoice_emission_ratio(self, move, sale_order):
        """
        Proporción de coupon_point.points a emitir en esta factura.

        Criterio Ana: el flete no está en las reglas y nunca genera puntos.
        - SO sin productos (solo envío) → 0
        - Factura que solo cobra envío (aunque la SO tenga productos) → 0
        - Factura de productos → product_invoiced / product_on_so (máx 1)

        Los puntos base ya vienen de las reglas del programa (categorías);
        aquí solo evitamos prorratear por el monto del flete.
        """
        so_product = self._osaka_so_product_total(sale_order)
        if not so_product:
            return 0.0
        inv_product = self._osaka_invoice_product_total(move, sale_order)
        if not inv_product:
            return 0.0
        return min(inv_product / so_product, 1.0)

    def _freeze_osaka_loyalty_snapshot(self):
        """Persiste el resumen calculado en este momento (post)."""
        for move in self:
            data = move._get_osaka_loyalty_summary_data_live()
            move.with_context(tracking_disable=True).write({
                'osaka_loyalty_summary_snapshot': data or False,
            })

    # -------------------------------------------------------------------------
    # Validación de Factura / Nota de Crédito
    # -------------------------------------------------------------------------
    def action_post(self):
        res = super().action_post()
        for move in self:
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue

            is_refund = move.move_type == 'out_refund'
            sale_orders = move.line_ids.sale_line_ids.order_id
            if not sale_orders:
                continue

            try:
                # Traza: Ligar el uso ('used') de la SO a esta Factura
                if not is_refund:
                    used_history_lines = self.env['loyalty.history'].sudo().search([
                        ('order_id', 'in', sale_orders.ids),
                        ('order_model', '=', 'sale.order'),
                        ('used', '>', 0),
                        ('invoice_id', '=', False),
                        ('card_id.program_id.osaka_program_type', 'in', ['puntos', 'amigos'])
                    ])
                    if used_history_lines:
                        used_history_lines.sudo().write({'invoice_id': move.id})

                # Generar Emisión ('issued') o Reversión
                for so in sale_orders:
                    # Criterio Ana: flete nunca aporta; ratio solo sobre productos
                    ratio = self._osaka_invoice_emission_ratio(move, so)

                    for coupon_point in so.coupon_point_ids:
                        program = coupon_point.coupon_id.program_id
                        if program.osaka_program_type not in ['puntos', 'amigos']:
                            continue

                        base_points = coupon_point.points * ratio
                        max_osaka_points = coupon_point.points

                        if is_refund:
                            # --- NOTA DE CRÉDITO ---
                            history_lines = self.env['loyalty.history'].sudo().search([
                                ('order_id', '=', so.id),
                                ('order_model', '=', 'sale.order'),
                                ('card_id', '=', coupon_point.coupon_id.id)
                            ])
                            already_issued = sum(history_lines.mapped('issued'))
                            points_to_revert = min(base_points, already_issued)
                            if points_to_revert > 0:
                                self.env['loyalty.history'].sudo().create({
                                    'order_id': so.id,
                                    'order_model': 'sale.order',
                                    'description': f"Nota de Crédito {move.name}",
                                    'card_id': coupon_point.coupon_id.id,
                                    'used': 0.0,
                                    'issued': -points_to_revert,
                                    'invoice_id': move.id,
                                    'is_reversal': True,
                                })
                        else:
                            # --- FACTURA (incluye re-confirmación: Opción B) ---
                            move_lines = self.env['loyalty.history'].sudo().search([
                                ('invoice_id', '=', move.id),
                                ('card_id', '=', coupon_point.coupon_id.id),
                            ])
                            net_on_move = sum(move_lines.mapped('issued'))

                            live_emission = move_lines.filtered(
                                lambda l: l.issued > 0
                                and not l.is_reversal
                                and not l.is_reversed
                            )

                            if live_emission and net_on_move > 0:
                                continue

                            history_lines = self.env['loyalty.history'].sudo().search([
                                ('order_id', '=', so.id),
                                ('order_model', '=', 'sale.order'),
                                ('card_id', '=', coupon_point.coupon_id.id)
                            ])
                            already_issued = sum(history_lines.mapped('issued'))

                            points_to_issue = min(
                                base_points,
                                max_osaka_points - already_issued,
                            )
                            if points_to_issue > 0:
                                # R6: siempre "Facturación" (también en re-post tras anulación)
                                self.env['loyalty.history'].sudo().create({
                                    'order_id': so.id,
                                    'order_model': 'sale.order',
                                    'description': f"Facturación {move.name}",
                                    'card_id': coupon_point.coupon_id.id,
                                    'used': 0.0,
                                    'issued': points_to_issue,
                                    'invoice_id': move.id,
                                })

            except Exception as e:
                _logger.error(f"Error procesando puntos Osaka en factura {move.id}: {e}")
                move.activity_schedule(
                    'mail.mail_activity_data_warning',
                    summary="Fallo en Lealtad Osaka",
                    note=f"No se pudieron emitir ni vincular puntos. Error: {str(e)}",
                    user_id=move.user_id.id or self.env.uid
                )

        # R4: congelar foto tras emitir/ligar historial (saldos ya sincronizados).
        # Incluye facturas de cliente aunque no hayan emitido puntos en este post.
        to_freeze = self.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund')
        )
        if to_freeze:
            to_freeze._freeze_osaka_loyalty_snapshot()

        return res

    # -------------------------------------------------------------------------
    # Anulación de Factura / Nota de Crédito
    # -------------------------------------------------------------------------
    def button_cancel(self):
        res = super().button_cancel()
        for move in self:
            history_lines = self.env['loyalty.history'].sudo().search([
                ('invoice_id', '=', move.id)
            ])
            if not history_lines:
                continue

            # Líneas de uso (de la SO): desligar siempre
            used_lines = history_lines.filtered(lambda l: l.used > 0)
            if used_lines:
                used_lines.sudo().write({'invoice_id': False})

            if move.move_type == 'out_invoice':
                # --- ANULACIÓN DE FACTURA (Opción B: conservar historial) ---
                cards_in_history = history_lines.filtered(
                    lambda l: l.issued != 0
                ).mapped('card_id')

                for card in cards_in_history:
                    card_lines = history_lines.filtered(
                        lambda l: l.card_id == card and l.issued != 0
                    )
                    net_issued = sum(card_lines.mapped('issued'))

                    if net_issued > 0:
                        source_line = card_lines.filtered(
                            lambda l: l.issued > 0 and not l.is_reversal
                        )[:1]

                        self.env['loyalty.history'].sudo().create({
                            'card_id': card.id,
                            'description': f"Reversión por Factura Anulada {move.name}",
                            'issued': -net_issued,
                            'invoice_id': move.id,
                            'is_reversal': True,
                            'order_id': source_line.order_id if source_line else False,
                            'order_model': source_line.order_model or 'sale.order' if source_line else False,
                        })

                        original_emissions = card_lines.filtered(
                            lambda l: l.issued > 0 and not l.is_reversal
                        )
                        if original_emissions:
                            original_emissions.sudo().write({'is_reversed': True})

            elif move.move_type == 'out_refund':
                nc_reversal_lines = history_lines.filtered(
                    lambda l: l.is_reversal and l.issued != 0
                )
                if nc_reversal_lines:
                    nc_reversal_lines.sudo().unlink()

            # R4: no regenerar snapshot en cancel — se conserva la foto del post.

        return res

    # -------------------------------------------------------------------------
    # Resumen de Puntos en Factura (PDF / Portal / Vista)
    # -------------------------------------------------------------------------
    def _get_osaka_loyalty_summary_data_live(self):
        """
        Resumen en vivo desde tarjetas + historial de esta factura.
        Usado al congelar snapshot y en borradores sin foto.
        """
        self.ensure_one()
        summary = []
        if not self.id or not self.partner_id:
            return summary

        commercial_partner = self.partner_id.commercial_partner_id

        all_cards = self.env['loyalty.card'].sudo().search([
            ('partner_id.commercial_partner_id', '=', commercial_partner.id),
            ('program_id.osaka_program_type', 'in', ['puntos', 'amigos'])
        ])

        history_lines = self.env['loyalty.history'].sudo().search([
            ('invoice_id', '=', self.id)
        ])

        for card in all_cards:
            card_lines = history_lines.filtered(lambda l: l.card_id == card)
            issued = sum(card_lines.mapped('issued'))
            used = sum(card_lines.mapped('used'))

            if card.points > 0 or card.puntos_a_vencer_este_mes > 0 or issued != 0 or used != 0:
                saldo_anterior = card.points - issued + used
                summary.append({
                    'program_name': card.program_id.name,
                    'saldo_anterior': saldo_anterior,
                    'issued': issued,
                    'used': used,
                    'total': card.points,
                    'expiring': card.puntos_a_vencer_este_mes,
                })

        return summary

    def _get_osaka_loyalty_summary_data(self):
        """
        Preferir snapshot congelado al validar; live solo sin foto (borrador / legado).
        """
        self.ensure_one()
        if self.osaka_loyalty_summary_snapshot:
            return self.osaka_loyalty_summary_snapshot
        return self._get_osaka_loyalty_summary_data_live()

    @api.depends('osaka_loyalty_summary_snapshot', 'partner_id', 'state')
    def _compute_osaka_loyalty_summary(self):
        for move in self:
            data = move._get_osaka_loyalty_summary_data() if move.id else []
            if not data:
                move.osaka_loyalty_summary_html = False
                continue

            move.osaka_loyalty_summary_html = self.env['ir.qweb']._render(
                'pgm_osaka_loyalty.template_osaka_loyalty_summary',
                {'osaka_summary': data}
            )
