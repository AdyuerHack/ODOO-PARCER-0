# -*- coding: utf-8 -*-

from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wms_inactivity_minutes = fields.Integer(
        string='Minutos de Inactividad WMS',
        config_parameter='pgm_wms_progress.inactivity_minutes',
        default=30,
        help="Tiempo en minutos sin escaneos para considerar inactividad y registrar tiempo muerto retroactivo."
    )
    wms_dead_time_closure_hours = fields.Integer(
        string='Horas Máximas Tiempo Muerto',
        config_parameter='pgm_wms_progress.dead_time_closure_hours',
        default=1,
        help="Si un tiempo muerto supera estas horas, se cierra automáticamente."
    )
