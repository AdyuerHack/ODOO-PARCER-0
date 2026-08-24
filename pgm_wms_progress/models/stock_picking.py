# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    progress_interval_ids = fields.One2many('stock.picking.progress.interval', 'picking_id', string='Intervalos de Progreso')
    progress_interval_count = fields.Integer(compute='_compute_progress_interval_count', string='Conteo de Intervalos')
    
    progreso_lineas = fields.Float(string='Progreso Líneas (%)', compute='_compute_progreso', store=True)
    progreso_unidades = fields.Float(string='Progreso Unidades (%)', compute='_compute_progreso', store=True)
    velocidad_wms = fields.Float(string='Velocidad WMS (Und/Hr)', compute='_compute_velocidad_wms', store=False)
    seguimiento_wms = fields.Boolean(related='picking_type_id.seguimiento_wms', string='Seguimiento WMS Activo')

    @api.model
    def _get_fields_stock_barcode(self):
        return [
            'seguimiento_wms',
        ] + super()._get_fields_stock_barcode()

    @api.depends('progress_interval_ids')
    def _compute_progress_interval_count(self):
        for picking in self:
            picking.progress_interval_count = len(picking.progress_interval_ids)
            
    @api.depends('move_line_ids.estado_linea', 'move_line_ids.quantity', 'move_line_ids.quantity_product_uom')
    def _compute_progreso(self):
        for picking in self:
            valid_lines = picking.move_line_ids.filtered(lambda l: not l.move_id.sale_line_id or l.move_id.sale_line_id.product_uom_qty > 0)
            
            # Progreso Líneas
            total_lines = len(valid_lines)
            done_lines = len(valid_lines.filtered(lambda l: l.estado_linea == 'ejecutada'))
            picking.progreso_lineas = (done_lines / total_lines * 100.0) if total_lines > 0 else 0.0
            
            # Progreso Unidades
            total_units = sum(valid_lines.mapped('quantity_product_uom'))
            done_units = sum(valid_lines.mapped('quantity'))
            picking.progreso_unidades = (done_units / total_units * 100.0) if total_units > 0 else 0.0

    def _compute_velocidad_wms(self):
        for picking in self:
            productive_intervals = picking.progress_interval_ids.filtered(lambda i: i.interval_type == 'productivo' and i.date_end)
            total_minutes = sum(i.duration_minutes for i in productive_intervals)
            total_units = sum(i.qty_done for i in productive_intervals)
            
            if total_minutes > 0:
                picking.velocidad_wms = (total_units / total_minutes) * 60.0
            else:
                picking.velocidad_wms = 0.0

    def action_view_progress_intervals(self):
        self.ensure_one()
        return {
            'name': 'Intervalos de Progreso',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.progress.interval',
            'view_mode': 'list',
            'domain': [('picking_id', '=', self.id)],
            'context': {'default_picking_id': self.id},
        }

    def button_validate(self):
        """
        Sobrescribe la validación para bloquear operaciones de Aduana WMS
        si existe alguna línea (producto) con peso de 0.00.
        """
        for picking in self:
            if picking.picking_type_id.is_aduana_wms:
                packages = picking.move_line_ids.mapped('result_package_id') | picking.move_line_ids.mapped('package_id')
                for package in packages:
                    if package.weight <= 0.0:
                        raise UserError(
                            f"Bloqueo OSAKA: No se puede validar la Aduana porque el paquete '{package.name}' tiene un peso de 0.00. "
                            f"Por favor configure el peso del paquete antes de continuar."
                        )
        return super(StockPicking, self).button_validate()
