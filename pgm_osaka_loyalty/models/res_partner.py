# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    loyalty_card_ids = fields.One2many(
        'loyalty.card', 'partner_id',
        string="Tarjetas de Lealtad",
    )

    def _get_osaka_cards_for_monthly_mail(self):
        """
        Retorna las tarjetas Osaka activas del grupo comercial de este partner
        (incluye tarjetas en contactos hijos) con saldo o puntos por vencer.
        Usado por la plantilla de correo mensual consolidada.
        """
        self.ensure_one()
        return self.env['loyalty.card'].search([
            ('partner_id.commercial_partner_id', '=', self.id),
            ('program_id.osaka_program_type', 'in', ['puntos', 'amigos']),
        ]).filtered(
            lambda c: c.points > 0 or c.puntos_a_vencer_este_mes > 0
        )
