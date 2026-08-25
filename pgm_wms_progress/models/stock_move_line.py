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

    @api.depends('quantity', 'picked', 'linea_cerrada_manual')
    def _compute_estado_linea(self):
        for line in self:
            if line.linea_cerrada_manual or line.picked:
                line.estado_linea = 'ejecutada'
            elif line.quantity > 0:
                line.estado_linea = 'en_proceso'
            else:
                line.estado_linea = 'sin_ejecutar'
