# -*- coding: utf-8 -*-

from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    progreso_picking_wms = fields.Float(string='Progreso Picking (%)', compute='_compute_wms_progress', store=False)
    velocidad_picking_wms = fields.Float(string='Velocidad Picking (Und/Hr)', compute='_compute_wms_progress', store=False)

    progreso_aduana_wms = fields.Float(string='Progreso Aduana (%)', compute='_compute_wms_progress', store=False)
    velocidad_aduana_wms = fields.Float(string='Velocidad Aduana (Und/Hr)', compute='_compute_wms_progress', store=False)

    progreso_entrega_wms = fields.Float(string='Progreso Entrega (%)', compute='_compute_wms_progress', store=False)
    velocidad_entrega_wms = fields.Float(string='Velocidad Entrega (Und/Hr)', compute='_compute_wms_progress', store=False)

    @api.depends('picking_ids.move_line_ids.estado_linea', 'picking_ids.move_line_ids.quantity', 'picking_ids.move_line_ids.quantity_product_uom', 'picking_ids.progress_interval_ids')
    def _compute_wms_progress(self):
        for order in self:
            pickings = order.picking_ids.filtered(lambda p: p.state not in ('draft', 'cancel'))
            
            def calculate_stage(is_type_field):
                stage_pickings = pickings.filtered(lambda p: getattr(p.picking_type_id, is_type_field, False))
                if not stage_pickings:
                    return 0.0, 0.0
                    
                # Progreso: Consolidado de move_lines válidas (basado en líneas en lugar de unidades)
                valid_lines = stage_pickings.mapped('move_line_ids').filtered(
                    lambda l: not l.move_id.sale_line_id or l.move_id.sale_line_id.product_uom_qty > 0
                )
                total_lines = len(valid_lines)
                done_lines = len(valid_lines.filtered(lambda l: l.estado_linea == 'ejecutada'))
                progreso = (done_lines / total_lines * 100.0) if total_lines > 0 else 0.0
                
                # Velocidad: Consolidado de intervalos productivos
                intervals = stage_pickings.mapped('progress_interval_ids').filtered(lambda i: i.interval_type == 'productivo' and i.date_end)
                total_minutes = sum(i.duration_minutes for i in intervals)
                total_units_done = sum(i.qty_done for i in intervals)
                velocidad = (total_units_done / total_minutes * 60.0) if total_minutes > 0 else 0.0
                
                return progreso, velocidad

            # Calculamos para Picking
            p_prog, p_vel = calculate_stage('is_picking_wms')
            order.progreso_picking_wms = p_prog
            order.velocidad_picking_wms = p_vel
            
            # Calculamos para Aduana
            a_prog, a_vel = calculate_stage('is_aduana_wms')
            order.progreso_aduana_wms = a_prog
            order.velocidad_aduana_wms = a_vel
            
            # Calculamos para Entrega
            e_prog, e_vel = calculate_stage('is_entrega_wms')
            order.progreso_entrega_wms = e_prog
            order.velocidad_entrega_wms = e_vel
