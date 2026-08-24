# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import pytz

class StockPickingProgressInterval(models.Model):
    _name = 'stock.picking.progress.interval'
    _description = 'Intervalo de Progreso WMS'
    _order = 'date_start desc'

    picking_id = fields.Many2one('stock.picking', string='Operación', required=True, ondelete='cascade', index=True)
    picking_type_id = fields.Many2one('stock.picking.type', related='picking_id.picking_type_id', store=True, string='Tipo Operación')
    user_id = fields.Many2one('res.users', string='Operario', required=True, default=lambda self: self.env.user)
    date_start = fields.Datetime(string='Fecha/hora inicio', required=True, default=fields.Datetime.now)
    date_end = fields.Datetime(string='Fecha/hora fin')
    interval_type = fields.Selection([
        ('productivo', 'Tiempo productivo'),
        ('muerto', 'Tiempo muerto')
    ], string='Tipo', required=True, default='productivo')
    qty_done = fields.Float(string='Cantidades', default=0.0)
    
    # Campo computado y almacenado para facilitar filtros del Dashboard
    hour_of_day = fields.Integer(string='Hora del día', compute='_compute_hour_of_day', store=True)

    @api.depends('date_start')
    def _compute_hour_of_day(self):
        for record in self:
            if record.date_start:
                # Convertir UTC a hora local del usuario para agrupar correctamente
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                local_time = pytz.utc.localize(record.date_start).astimezone(user_tz)
                record.hour_of_day = local_time.hour
            else:
                record.hour_of_day = 0

    def write(self, vals):
        """
        Bloquear modificaciones si el intervalo ya está cerrado (tiene date_end),
        salvo que el usuario pertenezca al grupo de corrección wms_corrector.
        Sin embargo, se permite asignar date_end si aún estaba abierto, o actualizar qty_done.
        """
        for record in self:
            # Si el registro ya estaba cerrado antes de esta modificación
            if record.date_end:
                # Y el usuario NO tiene el grupo de bypass de corrección
                if not self.env.user.has_group('pgm_wms_progress.group_wms_corrector'):
                    raise UserError(_("Inmutabilidad WMS: No se puede modificar un intervalo de tiempo que ya ha sido cerrado."))
        return super(StockPickingProgressInterval, self).write(vals)

    def unlink(self):
        """
        Bloquear eliminación de cualquier registro para mantener inmutabilidad.
        """
        for record in self:
            if not self.env.user.has_group('pgm_wms_progress.group_wms_corrector'):
                raise UserError(_("Inmutabilidad WMS: No se puede eliminar ningún intervalo de progreso."))
        return super(StockPickingProgressInterval, self).unlink()

    @api.depends('date_start', 'date_end')
    def _compute_duration_minutes(self):
        for record in self:
            if record.date_start and record.date_end:
                delta = record.date_end - record.date_start
                record.duration_minutes = delta.total_seconds() / 60.0
            else:
                record.duration_minutes = 0.0

    duration_minutes = fields.Float(string='Duración (min)', compute='_compute_duration_minutes', store=True)

    @api.model
    def _cron_failsafe_inactivity(self):
        """
        Busca intervalos productivos abiertos que no hayan tenido actividad. Los cierra y abre un muerto.
        También cierra los muertos muy largos según la configuración.
        """
        IrConfig = self.env['ir.config_parameter'].sudo()
        inactivity_minutes = int(IrConfig.get_param('pgm_wms_progress.inactivity_minutes', 30))
        dead_time_closure = int(IrConfig.get_param('pgm_wms_progress.dead_time_closure_hours', 1))
        
        now = fields.Datetime.now()
        
        # 1. Cierre de inactividad productiva
        open_productive = self.search([
            ('interval_type', '=', 'productivo'),
            ('date_end', '=', False)
        ])
        for interval in open_productive:
            last_activity = interval.write_date or interval.date_start
            delta = (now - last_activity).total_seconds() / 60.0
            
            if delta > inactivity_minutes:
                # Cerrar retroactivamente productivo
                interval.write({'date_end': last_activity})
                # Crear solo un muerto abierto desde la última actividad
                self.create({
                    'picking_id': interval.picking_id.id,
                    'user_id': interval.user_id.id,
                    'interval_type': 'muerto',
                    'date_start': last_activity,
                    'qty_done': 0,
                })
                
        # 2. Cierre de tiempos muertos largos
        open_dead = self.search([
            ('interval_type', '=', 'muerto'),
            ('date_end', '=', False)
        ])
        for dead in open_dead:
            delta_hours = (now - dead.date_start).total_seconds() / 3600.0
            if delta_hours > dead_time_closure:
                # Si excede las horas permitidas de tiempo muerto, cerrarlo forzosamente
                dead.write({'date_end': now})

    @api.model
    def _cron_split_hour(self):
        """
        Segmenta los intervalos abiertos si cambian de hora, basado en TZ de la compañía.
        """
        now_utc = fields.Datetime.now()
        company_tz = pytz.timezone(getattr(self.env.user, 'tz', None) or getattr(self.env.company.partner_id, 'tz', None) or 'UTC')
        now_local = pytz.utc.localize(now_utc).astimezone(company_tz)
        
        open_intervals = self.search([('date_end', '=', False)])
        
        for interval in open_intervals:
            start_local = pytz.utc.localize(interval.date_start).astimezone(company_tz)
            if start_local.hour != now_local.hour:
                # Cortamos a nivel exacto de la nueva hora en UTC
                cut_time_local = now_local.replace(minute=0, second=0, microsecond=0)
                cut_time_utc = cut_time_local.astimezone(pytz.utc).replace(tzinfo=None)
                
                interval.write({'date_end': cut_time_utc})
                
                self.create({
                    'picking_id': interval.picking_id.id,
                    'user_id': interval.user_id.id,
                    'interval_type': interval.interval_type,
                    'date_start': cut_time_utc,
                    'qty_done': 0,
                })
