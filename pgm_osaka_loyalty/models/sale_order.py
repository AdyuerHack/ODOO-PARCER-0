# -*- coding: utf-8 -*-

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _add_loyalty_history_lines(self):
        """
        Interceptamos la creación del historial en SO.
        Mantenemos la lógica nativa, pero para programas Osaka forzamos issued=0,
        porque la emisión (issued) solo debe ocurrir en la facturación.
        """
        res = super()._add_loyalty_history_lines()
        osaka_history = self.env['loyalty.history'].sudo().search([
            ('order_id', 'in', self.ids),
            ('order_model', '=', self._name),
            ('card_id.program_id.osaka_program_type', 'in', ['puntos', 'amigos'])
        ])
        if osaka_history:
            # Apagamos la emisión. El uso ('used') se mantiene para prevenir double-spending.
            osaka_history.sudo().write({'issued': 0.0})

            # Limpiar líneas basura que solo iban a emitir (quedaron 0/0)
            garbage_lines = osaka_history.filtered(lambda h: h.used == 0)
            if garbage_lines:
                garbage_lines.sudo().unlink()

        return res

    def _get_point_changes(self):
        """
        Neutralizamos la mutación nativa del Float (points) en SO para Osaka.
        Como hemos implementado un _sync_points_from_history() que escucha el CRUD
        de loyalty.history, si permitimos que Odoo sume/reste aquí, haríamos un doble descuento.
        """
        points_per_coupon = super()._get_point_changes()
        for coupon in list(points_per_coupon.keys()):
            if coupon.program_id.osaka_program_type in ['puntos', 'amigos']:
                # Eliminar el coupon del diccionario para que Odoo no mute el saldo directamente.
                del points_per_coupon[coupon]
        return points_per_coupon
