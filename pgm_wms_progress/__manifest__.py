# -*- coding: utf-8 -*-

{
    'name': 'Progreso y Velocidad WMS (OSAKA)',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Módulo para el seguimiento en tiempo real del progreso y la velocidad de operaciones logísticas en la PDA',
    'description': """
Progreso y Velocidad WMS
========================
Implementa el requerimiento "Progreso y velocidad WMS V3" para OSAKAPARTS:
- Registro inmutable de tiempos productivos y muertos por operario.
- Failsafe de backend con crons para cierre automático (inactividad y cambio de hora).
- Cálculo de progreso por líneas ejecutadas y unidades reservadas vs procesadas.
- Velocidad de picking, aduana y entrega.
- Vistas unificadas consolidadas desde Órdenes de Venta (Backorders no duplican progreso).
- Dashboards en tiempo real de unidades procesadas por empleado.
    """,
    'author': 'Progsum',
    'depends': [
        'base',
        'stock',
        'stock_barcode',
        'sale',
        'sale_management',
        'sale_stock',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/res_config_settings_views.xml',
        'views/stock_picking_type_views.xml',
        'views/stock_picking_progress_interval_views.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pgm_wms_progress/static/src/models/barcode_model.js',
            # 'pgm_wms_progress/static/src/components/main.xml',
            'pgm_wms_progress/static/src/components/dashboard/dashboard.js',
            'pgm_wms_progress/static/src/components/dashboard/dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
