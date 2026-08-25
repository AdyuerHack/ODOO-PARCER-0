# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError
import pytz
from datetime import datetime, timedelta

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def process_wms_scan(self, picking_id, action='scan', line_id=None):
        \"\"\"
        Punto de entrada principal RPC desde la PDA.
        Gestiona la lógica asíncrona de tiempos (Productivo/Muerto).
        action puede ser: 'scan', 'pause', 'play', 'close_line'
        \"\"\"
        picking = self.browse(picking_id)
        if not picking.exists() or not picking.picking_type_id.seguimiento_wms:
            return {'status': 'ignored'}
            
        now = fields.Datetime.now()
        user_id = self.env.user.id
        
        # Helper para obtener progreso actual
        def get_current_qty():
            valid_moves = picking.move_ids.filtered(lambda m: not m.sale_line_id or m.sale_line_id.product_uom_qty > 0)
            return sum(valid_moves.mapped('quantity'))
            
        IntervalModel = self.env['stock.picking.progress.interval']
        
        if action == 'close_line' and line_id:
            move_line = self.env['stock.move.line'].browse(line_id)
            if move_line.exists():
                move_line.write({'linea_cerrada_manual': True})
                return {'status': 'line_closed'}
                
        # 1. Aplicar Regla: Cambio transversal
        other_open_intervals = IntervalModel.search([
            ('user_id', '=', user_id),
            ('date_end', '=', False),
            ('picking_id', '!=', picking.id)
        ])
        for other in other_open_intervals:
            other.write({'date_end': now})
            
        # 2. Buscar intervalo activo actual en ESTE picking
        current_interval = IntervalModel.search([
            ('user_id', '=', user_id),
            ('picking_id', '=', picking.id),
            ('date_end', '=', False)
        ], limit=1)

        if action == 'pause':
            if current_interval and current_interval.interval_type == 'productivo':
                current_interval.write({'date_end': now})
                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'muerto',
                    'date_start': now,
                })
            return {'status': 'paused'}
            
        elif action == 'play':
            if current_interval and current_interval.interval_type == 'muerto':
                current_interval.write({'date_end': now})
                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'productivo',
                    'date_start': now,
                    'initial_picking_qty': get_current_qty(),
                })
            elif not current_interval:
                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'productivo',
                    'date_start': now,
                    'initial_picking_qty': get_current_qty(),
                })
            return {'status': 'playing'}
            
        elif action == 'scan':
            inactivity_minutes = int(self.env['ir.config_parameter'].sudo().get_param('pgm_wms_progress.inactivity_minutes', 30))
            
            if not current_interval:
                last_closed = IntervalModel.search([
                    ('user_id', '=', user_id),
                    ('picking_id', '=', picking.id),
                    ('interval_type', '=', 'productivo'),
                    ('date_end', '!=', False)
                ], order='date_end desc', limit=1)
                
                if last_closed and last_closed.date_end:
                    time_diff = (now - last_closed.date_end).total_seconds() / 60.0
                    if time_diff > inactivity_minutes:
                        IntervalModel.create({
                            'picking_id': picking.id,
                            'user_id': user_id,
                            'interval_type': 'muerto',
                            'date_start': last_closed.date_end,
                            'date_end': now
                        })

                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'productivo',
                    'date_start': now,
                    'initial_picking_qty': get_current_qty(),
                })
            else:
                if current_interval.interval_type == 'muerto':
                    current_interval.write({'date_end': now})
                    IntervalModel.create({
                        'picking_id': picking.id,
                        'user_id': user_id,
                        'interval_type': 'productivo',
                        'date_start': now,
                        'initial_picking_qty': get_current_qty(),
                    })
                else:
                    current_tz = pytz.timezone(self.env.user.tz or 'UTC')
                    start_local = pytz.utc.localize(current_interval.date_start).astimezone(current_tz)
                    now_local = pytz.utc.localize(now).astimezone(current_tz)
                    
                    if start_local.hour != now_local.hour:
                        end_of_hour = start_local.replace(minute=59, second=59, microsecond=999999).astimezone(pytz.utc).replace(tzinfo=None)
                        current_interval.write({'date_end': end_of_hour})
                        
                        start_of_new_hour = now_local.replace(minute=0, second=0, microsecond=0).astimezone(pytz.utc).replace(tzinfo=None)
                        IntervalModel.create({
                            'picking_id': picking.id,
                            'user_id': user_id,
                            'interval_type': 'productivo',
                            'date_start': start_of_new_hour,
                            'initial_picking_qty': get_current_qty(),
                        })
                    else:
                        # Si es el mismo intervalo y misma hora, no sumamos ciegamente +1.
                        # El cálculo de cantidades completadas (qty_done) lo realiza el modelo de forma computada.
                        # Forzamos una escritura vacía si quisiéramos actualizar write_date, pero ya nos apalancamos en el write_date del picking.
                        pass

            return {'status': 'scanned'}

        return {'status': 'unknown'}
