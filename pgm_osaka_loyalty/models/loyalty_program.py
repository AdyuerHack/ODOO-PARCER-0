# -*- coding: utf-8 -*-

from odoo import models, fields


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    osaka_program_type = fields.Selection(
        selection=[
            ('puntos', 'Puntos Osaka'),
            ('amigos', 'Amigos Osaka'),
            ('otro', 'Otro / No aplica')
        ],
        string="Tipo de Programa Osaka",
        default='otro',
        help="Clasificación para separar Puntos Osaka y Amigos Osaka en reportes y notificaciones."
    )
    validez_puntos_meses = fields.Integer(
        string="Validez de Puntos (Meses)",
        default=6,
        help="Horizonte real de caducidad Osaka (Regla B). "
             "Los puntos caducan N meses después de la fecha de facturación "
             "(cron diario FIFO). No confundir con el filtro de visualización "
             "oculto en la tarjeta ('Validez de puntos').",
    )
