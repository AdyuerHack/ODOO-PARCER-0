/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PreviewTableWidget extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            columns: [],
            rows: [],
        });

        onWillStart(async () => {
            await this.loadPreview();
        });
    }

    async loadPreview() {
        const recordId = this.props.record.resId;
        if (!recordId) {
            this.state.loading = false;
            return;
        }

        try {
            const rows = await this.orm.call("import.session", "get_preview_rows", [[recordId]]);
            if (rows && rows.length > 0) {
                this.state.columns = Object.keys(rows[0]);
                this.state.rows = rows;
            }
        } catch (e) {
            console.error("Error loading preview:", e);
        } finally {
            this.state.loading = false;
        }
    }
}

PreviewTableWidget.template = "smart_data_importer.PreviewTable";
PreviewTableWidget.props = {
    ...standardFieldProps,
};

registry.category("fields").add("preview_table", {
    component: PreviewTableWidget,
});
