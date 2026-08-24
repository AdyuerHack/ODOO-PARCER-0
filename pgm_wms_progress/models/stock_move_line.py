# -*- coding: utf-8 -*-

from odoo import models, fields, api

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    linea_cerrada_manual = fields.Boolean(
        string='Cerrada Manualmente',
        default=False,
        help="Indica si el operario cerró forzosamente esta línea desde la PDA."
    )
    
    estado_linea = fields.Selection([
        ('sin_ejecutar', 'Sin ejecutar'),
        ('en_proceso', 'En proceso'),
        ('ejecutada', 'Ejecutada')
    ], string='Estado Línea', compute='_compute_estado_linea', store=True)

    @api.depends('quantity', 'quantity_product_uom', 'linea_cerrada_manual')
    def _compute_estado_linea(self):
        for line in self:
            # En Odoo 19, 'quantity' suele ser la cantidad hecha y 'quantity_product_uom' la reservada, 
            # pero ajustaremos según el comportamiento exacto de reservas de Odoo 19.
            # Asumimos quantity_product_uom como reservado y quantity como procesado por el operario.
            qty_done = line.quantity or 0.0
            qty_reserved = line.quantity_product_uom or 0.0

            if line.linea_cerrada_manual:
                line.estado_linea = 'ejecutada'
            elif qty_done == 0.0:
                line.estado_linea = 'sin_ejecutar'
            elif qty_done >= qty_reserved and qty_reserved > 0:
                line.estado_linea = 'ejecutada'
            else:
                line.estado_linea = 'en_proceso'
