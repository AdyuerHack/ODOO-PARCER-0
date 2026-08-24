# -*- coding: utf-8 -*-

from odoo import api, models, fields


class LoyaltyHistory(models.Model):
    _inherit = 'loyalty.history'

    invoice_id = fields.Many2one('account.move', string="Factura", help="Factura relacionada a la generación o uso de estos puntos.")
    f_creacion_factura = fields.Date(related='invoice_id.invoice_date', string="F. Creación Factura", store=True)
    f_vencimiento_factura = fields.Date(related='invoice_id.invoice_date_due', string="F. Venc. Factura", store=True)
    f_vencimiento_puntos = fields.Date(string="F. Venc. Puntos", help="Se llena automáticamente cuando el cron expira los puntos")
    vencidos = fields.Float(string="Vencidos", default=0.0, help="Puntos de esta línea que ya caducaron.")
    is_reversal = fields.Boolean(
        "Es Reversión", default=False,
        help="Indica que esta línea es una contrapartida (NC o Anulación).",
    )
    is_reversed = fields.Boolean(
        "Emisión Revertida", default=False,
        help="Emisión original anulada; queda solo para auditoría. "
             "No cuenta en FIFO ni como emisión viva.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('card_id')._sync_points_from_history()
        return records

    def write(self, vals):
        res = super().write(vals)
        if any(field in vals for field in ['issued', 'used', 'vencidos', 'is_reversed']):
            self.mapped('card_id')._sync_points_from_history()
        return res

    def unlink(self):
        cards = self.mapped('card_id')
        res = super().unlink()
        cards._sync_points_from_history()
        return res
