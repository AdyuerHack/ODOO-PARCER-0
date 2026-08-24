# -*- coding: utf-8 -*-

from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dias_vencimiento_factura = fields.Integer(
        string="Días de gracia para vencimiento",
        config_parameter='pgm_osaka_loyalty.dias_vencimiento_factura',
        default=5,
        help="Días después del vencimiento de la factura en los que los puntos caducarán."
    )
