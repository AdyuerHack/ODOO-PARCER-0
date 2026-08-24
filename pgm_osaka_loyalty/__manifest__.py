# -*- coding: utf-8 -*-
{
    'name': 'Puntos y Vencimientos Osaka',
    'version': '19.0.2.2.0',
    'category': 'Sales/Loyalty',
    'summary': 'Gestión de vencimiento de puntos Osaka y Amigos Osaka.',
    'description': """
    Módulo para gestionar el vencimiento de puntos Osaka y Amigos Osaka.
    - Los puntos se asocian a facturas en lugar de órdenes de venta.
    - Se configuran días de gracia para el vencimiento de facturas.
    - Notificaciones mensuales automáticas consolidadas por cliente.
    - Trazabilidad completa de reversiones (NC y anulaciones).
    """,
    'author': 'Progsum',
    'website': 'https://www.progsum.com',
    'depends': [
        'base',
        'loyalty',
        'sale_loyalty',
        'account',
        'sale_management',
    ],
    'data': [
        'data/ir_cron.xml',
        'data/mail_template.xml',
        'views/res_config_settings_views.xml',
        'views/loyalty_program_views.xml',
        'views/loyalty_card_views.xml',
        'views/account_move_views.xml',
        'views/osaka_loyalty_templates.xml',
        'report/account_move_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
