/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class WmsProgressDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        
        this.hourlyCanvas = useRef("hourlyCanvas");
        this.dailyCanvas = useRef("dailyCanvas");
        this.pieCanvas = useRef("pieCanvas");

        this.charts = {};
        
        this.state = useState({
            hourlyData: {},
            dailyData: {},
            pieData: {},
            colors: {}, // Almacena color persistente por user_id
        });

        // Generador de colores consistentes
        this.getColor = (userId, userName) => {
            if (!this.state.colors[userId]) {
                const hash = userName.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
                const hue = hash % 360;
                this.state.colors[userId] = `hsl(${hue}, 70%, 50%)`;
            }
            return this.state.colors[userId];
        };

        onWillStart(async () => {
            try {
                await loadJS("/web/static/lib/Chart/Chart.js");
            } catch (e) {
                try {
                    await loadJS("/web/static/lib/chart.js/chart.js");
                } catch (e2) {
                    console.warn("Could not load Chart.js locally, trying CDN");
                    await loadJS("https://cdn.jsdelivr.net/npm/chart.js");
                }
            }
            await this.fetchData();
        });

        onMounted(() => {
            this.renderCharts();
            // Auto-refresh cada 5 mins
            this.intervalId = setInterval(async () => {
                await this.fetchData();
                this.renderCharts();
            }, 5 * 60 * 1000);
        });

        onWillUnmount(() => {
            if (this.intervalId) clearInterval(this.intervalId);
            Object.values(this.charts).forEach(c => c.destroy());
        });
    }

    async fetchData() {
        const today = new Date();
        const limitDate = new Date(today.getTime() - (15 * 24 * 60 * 60 * 1000));
        
        const intervals = await this.orm.searchRead(
            "stock.picking.progress.interval",
            [
                ["interval_type", "=", "productivo"], 
                ["date_start", ">=", limitDate.toISOString().split("T")[0]],
                ["picking_type_id.seguimiento_wms", "=", true]
            ],
            ["user_id", "qty_done", "date_start", "hour_of_day"]
        );

        const hourly = {};
        const dailyTotal = {};
        const pie = {};
        
        const todayStr = today.toISOString().split("T")[0];

        intervals.forEach(i => {
            const uid = i.user_id[0];
            const uname = i.user_id[1];
            const dateStr = i.date_start.split(" ")[0];
            const hour = i.hour_of_day;
            const qty = i.qty_done || 0;
            
            // Hourly
            if (!hourly[uname]) hourly[uname] = { data: Array(24).fill(0), color: this.getColor(uid, uname) };
            if (dateStr === todayStr) {
                hourly[uname].data[hour] += qty;
            }

            // Daily (Global Total)
            if (!dailyTotal[dateStr]) dailyTotal[dateStr] = 0;
            dailyTotal[dateStr] += qty;

            // Pie (Global % last 15 days)
            if (!pie[uname]) pie[uname] = { total: 0, color: this.getColor(uid, uname) };
            pie[uname].total += qty;
        });

        this.state.hourlyData = hourly;
        this.state.dailyData = dailyTotal;
        this.state.pieData = pie;
    }

    renderCharts() {
        if (!window.Chart) return;

        // Limpiar gráficas viejas
        Object.values(this.charts).forEach(c => c.destroy());

        const users = Object.keys(this.state.hourlyData);
        
        // 1. Hourly Chart (Unidades x Hora Hoy)
        if (this.hourlyCanvas.el) {
            this.charts.hourly = new Chart(this.hourlyCanvas.el, {
                type: 'line',
                data: {
                    labels: Array.from({length: 24}, (_, i) => `${i}:00`),
                    datasets: users.map(u => ({
                        label: u,
                        data: this.state.hourlyData[u].data,
                        borderColor: this.state.hourlyData[u].color,
                        fill: false
                    }))
                },
                options: { responsive: true, title: { display: true, text: 'Unidades por Hora (Hoy)' } }
            });
        }

        // 2. Daily Chart (Últimos 15 días - Total Consolidado)
        if (this.dailyCanvas.el) {
            const days = Object.keys(this.state.dailyData).sort();

            this.charts.daily = new Chart(this.dailyCanvas.el, {
                type: 'bar',
                data: {
                    labels: days,
                    datasets: [{
                        label: 'Total Unidades (Todos los operarios)',
                        data: days.map(d => this.state.dailyData[d]),
                        backgroundColor: 'hsl(210, 70%, 50%)', // Un azul genérico para el total
                    }]
                },
                options: { responsive: true, title: { display: true, text: 'Total de Unidades por Día (Últ. 15 Días)' } }
            });
        }

        // 3. Pie Chart
        if (this.pieCanvas.el) {
            const pieUsers = Object.keys(this.state.pieData);
            this.charts.pie = new Chart(this.pieCanvas.el, {
                type: 'doughnut',
                data: {
                    labels: pieUsers,
                    datasets: [{
                        data: pieUsers.map(u => this.state.pieData[u].total),
                        backgroundColor: pieUsers.map(u => this.state.pieData[u].color),
                    }]
                },
                options: { responsive: true, title: { display: true, text: 'Contribución Global' } }
            });
        }
    }
}

WmsProgressDashboard.template = "pgm_wms_progress.Dashboard";
registry.category("actions").add("wms_progress_dashboard", WmsProgressDashboard);
