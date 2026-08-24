/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BarcodeModel } from "@stock_barcode/models/barcode_model";

patch(BarcodeModel.prototype, "pgm_wms_progress.BarcodeModel", {
    async processBarcode(barcode) {
        // Interceptamos el escaneo normal
        const res = await super.processBarcode(...arguments);
        
        // Llamada asíncrona al backend para registrar el tiempo WMS
        // Solo si la operación existe y el escaneo parece ser exitoso
        if (this.record && this.record.id && res !== false) {
            this.orm.call("stock.picking", "process_wms_scan", [this.record.id], {
                action: 'scan'
            }).catch((err) => {
                console.error("Error al registrar escaneo WMS", err);
            });
        }
        
        return res;
    },

    async actionWmsPause() {
        if (this.record && this.record.id) {
            await this.orm.call("stock.picking", "process_wms_scan", [this.record.id], {
                action: 'pause'
            });
            this.notification.add("Tiempo Pausado", { type: "info" });
        }
    },

    async actionWmsPlay() {
        if (this.record && this.record.id) {
            await this.orm.call("stock.picking", "process_wms_scan", [this.record.id], {
                action: 'play'
            });
            this.notification.add("Tiempo Reanudado", { type: "success" });
        }
    },

    async actionWmsCloseLine(line) {
        if (this.record && this.record.id && line.id) {
            await this.orm.call("stock.picking", "process_wms_scan", [this.record.id], {
                action: 'close_line',
                line_id: line.id
            });
            this.notification.add("Línea cerrada forzosamente", { type: "warning" });
            // Forzar recarga o actualización visual si es necesario
            if (typeof this.trigger === 'function') {
                this.trigger('update');
            }
        }
    }
});
