# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError
import pytz
from datetime import datetime, timedelta

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def process_wms_scan(self, picking_id, action='scan', line_id=None):
        """
        Punto de entrada principal RPC desde la PDA.
        Gestiona la lógica asíncrona de tiempos (Productivo/Muerto).
        action puede ser: 'scan', 'pause', 'play', 'close_line'
        """
        picking = self.browse(picking_id)
        if not picking.exists() or not picking.picking_type_id.seguimiento_wms:
            return {'status': 'ignored'}
            
        now = fields.Datetime.now()
        user_id = self.env.user.id
        
        # Buscar intervalo activo actual del usuario para este picking
        IntervalModel = self.env['stock.picking.progress.interval']
        
        if action == 'close_line' and line_id:
            move_line = self.env['stock.move.line'].browse(line_id)
            if move_line.exists():
                move_line.write({'linea_cerrada_manual': True})
                return {'status': 'line_closed'}
                
        # 1. Aplicar Regla: Cambio transversal
        # Cerrar cualquier otro intervalo abierto de este usuario en OTRO picking
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
                # Iniciar tiempo muerto manual
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
                # Iniciar tiempo productivo manual
                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'productivo',
                    'date_start': now,
                    'qty_done': 0, # Se incrementará en el próximo escaneo real
                })
            elif not current_interval:
                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'productivo',
                    'date_start': now,
                    'qty_done': 0,
                })
            return {'status': 'playing'}
            
        elif action == 'scan':
            # Obtener umbral de inactividad de los settings
            inactivity_minutes = int(self.env['ir.config_parameter'].sudo().get_param('pgm_wms_progress.inactivity_minutes', 30))
            
            if not current_interval:
                # Caso especial: El usuario podría tener un intervalo productivo previo que cerró pero
                # queremos ver si pasó demasiado tiempo desde su último escaneo.
                # Para simplificar en Fase 2, si no hay actual, abrimos uno.
                # PERO primero revisamos si hubo inactividad excesiva buscando el último cerrado.
                last_closed = IntervalModel.search([
                    ('user_id', '=', user_id),
                    ('picking_id', '=', picking.id),
                    ('interval_type', '=', 'productivo'),
                    ('date_end', '!=', False)
                ], order='date_end desc', limit=1)
                
                if last_closed and last_closed.date_end:
                    time_diff = (now - last_closed.date_end).total_seconds() / 60.0
                    if time_diff > inactivity_minutes:
                        # Regla 30 min inactividad: se asume que todo ese tiempo fue muerto
                        IntervalModel.create({
                            'picking_id': picking.id,
                            'user_id': user_id,
                            'interval_type': 'muerto',
                            'date_start': last_closed.date_end,
                            'date_end': now
                        })

                # Ahora sí, abrimos el nuevo productivo y le sumamos 1 unidad
                IntervalModel.create({
                    'picking_id': picking.id,
                    'user_id': user_id,
                    'interval_type': 'productivo',
                    'date_start': now,
                    'qty_done': 1,
                })
            else:
                if current_interval.interval_type == 'muerto':
                    # Si escanea estando en pausa/muerto, automáticamente pasa a Play
                    current_interval.write({'date_end': now})
                    IntervalModel.create({
                        'picking_id': picking.id,
                        'user_id': user_id,
                        'interval_type': 'productivo',
                        'date_start': now,
                        'qty_done': 1,
                    })
                else:
                    # Regla Split Hora Exacta (cruce de hora)
                    # Revisar si el intervalo actual cruzó a una hora distinta a la actual
                    current_tz = pytz.timezone(self.env.user.tz or 'UTC')
                    start_local = pytz.utc.localize(current_interval.date_start).astimezone(current_tz)
                    now_local = pytz.utc.localize(now).astimezone(current_tz)
                    
                    if start_local.hour != now_local.hour:
                        # Cruzó la hora, cerrar el viejo al filo de la hora anterior
                        # Ejemplo: empezó a las 09:45, ahora son las 10:02
                        # Cerrar a las 09:59:59
                        end_of_hour = start_local.replace(minute=59, second=59, microsecond=999999).astimezone(pytz.utc).replace(tzinfo=None)
                        current_interval.write({'date_end': end_of_hour})
                        
                        # Abrir el nuevo a las 10:00:00 (o ahora)
                        start_of_new_hour = now_local.replace(minute=0, second=0, microsecond=0).astimezone(pytz.utc).replace(tzinfo=None)
                        IntervalModel.create({
                            'picking_id': picking.id,
                            'user_id': user_id,
                            'interval_type': 'productivo',
                            'date_start': start_of_new_hour,
                            'qty_done': 1,
                        })
                    else:
                        # Está en la misma hora, simplemente sumar cantidad y actualizar write_date (automático en Odoo)
                        # Pero Odoo no actualiza write_date si no cambia el valor, forzaremos si es necesario.
                        # Para inmutabilidad permitimos update de qty_done si date_end es False.
                        current_interval.write({
                            'qty_done': current_interval.qty_done + 1
                        })

            return {'status': 'scanned'}

        return {'status': 'unknown'}
