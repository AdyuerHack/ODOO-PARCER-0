from odoo import api, fields, models
from odoo.tools import format_amount
from dateutil.relativedelta import relativedelta


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    # Campo de selección para elegir la validez de los puntos
    pgm_points_validity_months = fields.Selection(
        selection=[
            ('all', 'Siempre (todos los puntos)'),
            ('3d', 'Solo últimos 3 días'),
            ('3', 'Solo últimos 3 meses'),
            ('6', 'Solo últimos 6 meses'),
            ('8', 'Solo últimos 8 meses'),
            ('12', 'Solo últimos 12 meses'),
            ('18', 'Solo últimos 18 meses'),
            ('24', 'Solo últimos 24 meses'),
        ],
        string="Validez de puntos",
        default='all',
        help="Selecciona el período desde el que se cuentan los puntos acumulados."
    )

    # Campo calculado y almacenado usado para cálculos y seguimiento (chatter)
    pgm_points_calculated = fields.Float(
        string="Puntos calculados",
        compute='_compute_pgm_points_calculated',
        store=True,
        digits=(16, 2),
        help="Valor calculado según la validez de puntos y movimientos.",
        tracking=True,
    )


    @api.depends('points', 'pgm_points_validity_months', 'history_ids', 'program_id')
    def _compute_pgm_points_calculated(self):
        """
        Calcula los puntos a mostrar según la validez seleccionada.
        Solo cuenta los movimientos dentro del período especificado.
        """
        for card in self:
            # Obtener los puntos totales de la tarjeta
            total_points = card.points
            selected_months = card.pgm_points_validity_months

            # Programas Osaka: el saldo contable ya aplica caducidad real
            # (validez_puntos_meses + cron). No filtrar por horizonte de display.
            osaka_type = getattr(card.program_id, 'osaka_program_type', 'otro')
            if osaka_type in ('puntos', 'amigos'):
                points_to_show = total_points
            # Si la tarjeta no tiene historial o la validez es 'all', mostrar todos los puntos
            elif selected_months == 'all' or not card.history_ids:
                points_to_show = total_points
            else:
                # Calcular la fecha de corte según la selección
                if selected_months == '3d':
                    cutoff_date = fields.Date.today() - relativedelta(days=3)
                else:
                    months_int = int(selected_months)
                    cutoff_date = fields.Date.today() - relativedelta(months=months_int)
                
                # Sumar y restar los movimientos dentro del período
                filtered_points = 0.0
                
                for move in card.history_ids:
                    # Obtener la fecha del movimiento (usar create_date si no hay date)
                    # NOTA: Si tu modelo tiene 'date' usa move.date, si no usa move.create_date
                    move_date = move.date if hasattr(move, 'date') else fields.Date.to_date(move.create_date)
                    if not move_date or move_date < cutoff_date:
                        continue

                    issued_amount = getattr(move, 'issued', 0.0) or 0.0
                    used_amount = getattr(move, 'used', 0.0) or 0.0

                    filtered_points += issued_amount
                    if used_amount > 0:
                        filtered_points -= used_amount

                points_to_show = filtered_points if filtered_points != 0 else 0.0

            # Guardar el valor calculado para uso interno y seguimiento (chatter)
            card.pgm_points_calculated = points_to_show


    @api.depends('pgm_points_calculated', 'point_name')
    def _compute_points_display(self):
        """
        Calcula el string a mostrar en la interfaz basado en los puntos calculados.
        """
        for card in self:
            card.points_display = card._format_points(card.pgm_points_calculated)

    def _format_points(self, points):
        """
        Formatea los puntos según la moneda o el nombre del punto.
        Método original sin modificar.
        """
        self.ensure_one()
        if self.program_id.currency_id and self.point_name == self.program_id.currency_id.symbol:
            return format_amount(self.env, points, self.program_id.currency_id)
        if points == int(points):
            return f"{int(points)} {self.point_name or ''}"
        return f"{points:.2f} {self.point_name or ''}"