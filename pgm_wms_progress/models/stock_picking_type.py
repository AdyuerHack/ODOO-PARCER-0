# -*- coding: utf-8 -*-

from odoo import api, models, fields

class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    seguimiento_wms = fields.Boolean(
        string='Seguimiento WMS',
        help="Si está marcado, habilita el rastreo de progreso, velocidad y tiempos en la PDA para este tipo de operación."
    )
    is_aduana_wms = fields.Boolean(
        string='Es Aduana (WMS)',
        help="Identifica de forma segura que esta operación es una Aduana."
    )
    is_picking_wms = fields.Boolean(
        string='Es Picking (WMS)',
        help="Identifica de forma segura que esta operación es un Picking."
    )
    is_entrega_wms = fields.Boolean(
        string='Es Entrega (WMS)',
        help="Identifica de forma segura que esta operación es una Entrega Final."
    )
    is_recibo_pt_wms = fields.Boolean(
        string='Es Recibo PT (WMS)',
        help="Identifica de forma segura que esta operación es un Recibo de Producto Terminado."
    )
