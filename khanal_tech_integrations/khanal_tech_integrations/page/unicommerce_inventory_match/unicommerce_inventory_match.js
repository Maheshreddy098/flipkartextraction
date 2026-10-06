frappe.pages['unicommerce-inventory-match'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Unicommerce Inventory Match',
		single_column: true,
	});

	const API = 'khanal_tech_integrations.unicommerce.api.ops';

	function esc(v) {
		const s = String(v === undefined || v === null ? '' : v);
		return frappe.utils && frappe.utils.escape_html ? frappe.utils.escape_html(s)
			: s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
	}
	function fmt(v) {
		const n = Number(v || 0);
		return Number.isFinite(n) ? n.toLocaleString('en-IN') : '0';
	}

	$(wrapper).find('.page-content').html(`
<div style="max-width:1180px;margin:18px auto 40px;">
	<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
		<div style="font-size:12px;color:#6c757d;">EC-FG (SAP) vs Unicommerce facility inventory (KFL ecom warehouse)</div>
		<div style="display:flex;gap:8px;flex-wrap:wrap;">
			<button id="btn-back-ops" class="btn btn-default btn-sm">Back to Ops Center</button>
			<button id="btn-refresh-match" class="btn btn-primary btn-sm">Refresh Match</button>
		</div>
	</div>

	<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px;">
		<input id="filter-item-code" type="text" class="form-control form-control-sm" placeholder="Filter item code" style="width:200px;">
		<input id="filter-batch-number" type="text" class="form-control form-control-sm" placeholder="Filter batch number" style="width:200px;">
		<input id="filter-limit" type="number" class="form-control form-control-sm" value="200" min="20" max="1000" style="width:110px;">
		<button id="btn-apply-filter" class="btn btn-default btn-sm">Apply</button>
		<button id="btn-clear-filter" class="btn btn-default btn-sm">Clear</button>
	</div>
	<div style="font-size:11px;color:#6c757d;margin-bottom:10px;">Filters apply to SAP, Unicommerce, and mismatch sections.</div>

	<div id="match-meta" style="font-size:12px;color:#6c757d;margin-bottom:10px;">Loading…</div>
	<div id="match-cards" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px;"></div>
	<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:12px;">
		<div style="border:1px solid #e9ecef;border-radius:8px;background:#fff;overflow:hidden;">
			<div style="padding:8px 10px;background:#f8f9fa;border-bottom:1px solid #e9ecef;font-size:12px;font-weight:700;">SAP EC-FG Inventory</div>
			<div id="sap-table-wrap" style="max-height:420px;overflow:auto;"></div>
		</div>
		<div style="border:1px solid #e9ecef;border-radius:8px;background:#fff;overflow:hidden;">
			<div style="padding:8px 10px;background:#f8f9fa;border-bottom:1px solid #e9ecef;font-size:12px;font-weight:700;">Unicommerce Inventory</div>
			<div id="uc-table-wrap" style="max-height:420px;overflow:auto;"></div>
		</div>
	</div>
	<div style="margin-top:12px;border:1px solid #e9ecef;border-radius:8px;background:#fff;overflow:hidden;">
		<div style="padding:8px 10px;background:#f8f9fa;border-bottom:1px solid #e9ecef;font-size:12px;font-weight:700;">Mismatches</div>
		<div id="mismatch-table-wrap" style="max-height:520px;overflow:auto;"></div>
	</div>
</div>
	`);

	function load_match(refresh = 0) {
		const item_code = $(wrapper).find('#filter-item-code').val().trim();
		const batch_number = $(wrapper).find('#filter-batch-number').val().trim();
		const limit = parseInt($(wrapper).find('#filter-limit').val() || '200', 10);
		$('#match-meta').text('Loading…');
		$('#sap-table-wrap').html('<div style="padding:12px;font-size:12px;color:#6c757d;">Loading SAP inventory…</div>');
		$('#uc-table-wrap').html('<div style="padding:12px;font-size:12px;color:#6c757d;">Loading Unicommerce inventory…</div>');
		$('#mismatch-table-wrap').html('<div style="padding:12px;font-size:12px;color:#6c757d;">Loading mismatch rows…</div>');

		frappe.call({
			method: API + '.ops_inventory_match_view',
			args: { refresh: refresh ? 1 : 0, item_code, batch_number, limit },
			freeze: false,
			callback: function (r) {
				if (!r.message) return;
				render_match(r.message);
			},
			error: function () {
				$('#match-meta').html('<span style="color:#dc3545;">Failed to load inventory match data.</span>');
			},
		});
	}

	function render_match(data) {
		const sap_rows = data.sap_rows || [];
		const uc_rows = data.uc_rows || [];
		const mismatch_rows = data.mismatch_rows || [];
		$('#match-meta').text(
			`Warehouse: ${data.warehouse_code || 'EC-FG'} | UC Facility: ${data.facility_code || '-'} | Last fetched: ${frappe.datetime.prettyDate(data.generated_at)} | Source: ${data.source || 'unknown'}`
		);
		$('#match-cards').html(`
			<div style="border:1px solid #e9ecef;border-radius:8px;padding:10px 12px;min-width:130px;"><div style="font-size:11px;color:#6c757d;">Items Compared</div><div style="font-size:22px;font-weight:700;">${fmt(data.item_count)}</div></div>
			<div style="border:1px solid #e9ecef;border-radius:8px;padding:10px 12px;min-width:130px;"><div style="font-size:11px;color:#6c757d;">SAP Rows</div><div style="font-size:22px;font-weight:700;">${fmt(sap_rows.length)}</div></div>
			<div style="border:1px solid #e9ecef;border-radius:8px;padding:10px 12px;min-width:130px;"><div style="font-size:11px;color:#6c757d;">UC Rows</div><div style="font-size:22px;font-weight:700;">${fmt(uc_rows.length)}</div></div>
			<div style="border:1px solid #e9ecef;border-radius:8px;padding:10px 12px;min-width:130px;"><div style="font-size:11px;color:#6c757d;">Matched</div><div style="font-size:22px;font-weight:700;color:#28a745;">${fmt(data.matched_count)}</div></div>
			<div style="border:1px solid #e9ecef;border-radius:8px;padding:10px 12px;min-width:130px;"><div style="font-size:11px;color:#6c757d;">Mismatches</div><div style="font-size:22px;font-weight:700;color:#dc3545;">${fmt(data.mismatch_count)}</div></div>
			<div style="border:1px solid #e9ecef;border-radius:8px;padding:10px 12px;min-width:130px;"><div style="font-size:11px;color:#6c757d;">Total Delta Qty</div><div style="font-size:22px;font-weight:700;color:#fd7e14;">${fmt(data.total_delta_qty)}</div></div>
		`);

		$('#sap-table-wrap').html(sap_rows.length ? `
			<table class="table table-bordered" style="margin:0;font-size:12px;min-width:320px;">
				<thead><tr style="position:sticky;top:0;background:#f8f9fa;z-index:1;"><th>Item Code</th><th>Batch Number</th><th style="text-align:right;">SAP Qty</th></tr></thead>
				<tbody>${sap_rows.map(row => `<tr><td style="font-weight:600;">${esc(row.item_code || '-')}</td><td>${esc(row.batch_number || '-')}</td><td style="text-align:right;">${fmt(row.sap_qty)}</td></tr>`).join('')}</tbody>
			</table>
		` : '<div style="padding:12px;font-size:12px;color:#6c757d;">No SAP inventory rows for selected filters.</div>');

		$('#uc-table-wrap').html(uc_rows.length ? `
			<table class="table table-bordered" style="margin:0;font-size:12px;min-width:320px;">
				<thead><tr style="position:sticky;top:0;background:#f8f9fa;z-index:1;"><th>Item Code</th><th>Batch Number</th><th style="text-align:right;">UC Qty</th></tr></thead>
				<tbody>${uc_rows.map(row => `<tr><td style="font-weight:600;">${esc(row.item_code || '-')}</td><td>${esc(row.batch_number || '-')}</td><td style="text-align:right;">${fmt(row.uc_qty)}</td></tr>`).join('')}</tbody>
			</table>
		` : '<div style="padding:12px;font-size:12px;color:#6c757d;">No Unicommerce inventory rows for selected filters.</div>');

		$('#mismatch-table-wrap').html(mismatch_rows.length ? `
			<table class="table table-bordered" style="margin:0;font-size:12px;min-width:920px;">
				<thead>
					<tr style="position:sticky;top:0;background:#f8f9fa;z-index:1;">
						<th>Item Code</th>
						<th style="text-align:right;">SAP Qty</th>
						<th style="text-align:right;">UC Qty</th>
						<th style="text-align:right;">Delta</th>
						<th style="text-align:right;">Batch Mismatches</th>
					</tr>
				</thead>
				<tbody>
					${mismatch_rows.map(row => `
						<tr>
							<td style="font-weight:600;">${esc(row.item_code || '-')}</td>
							<td style="text-align:right;">${fmt(row.sap_qty)}</td>
							<td style="text-align:right;">${fmt(row.uc_qty)}</td>
							<td style="text-align:right;color:${Math.abs(Number(row.delta_qty || 0)) > 0.001 ? '#dc3545' : '#28a745'};font-weight:600;">${fmt(row.delta_qty)}</td>
							<td style="text-align:right;">${fmt(row.batch_mismatch_count)}</td>
						</tr>
					`).join('')}
				</tbody>
			</table>
		` : '<div style="padding:12px;font-size:12px;color:#6c757d;">No mismatch rows for selected filters.</div>');
	}

	$(wrapper).find('#btn-refresh-match').on('click', () => load_match(1));
	$(wrapper).find('#btn-apply-filter').on('click', () => load_match(0));
	$(wrapper).find('#btn-clear-filter').on('click', function () {
		$(wrapper).find('#filter-item-code').val('');
		$(wrapper).find('#filter-batch-number').val('');
		$(wrapper).find('#filter-limit').val('200');
		load_match(0);
	});
	$(wrapper).find('#btn-back-ops').on('click', () => frappe.set_route('unicommerce-ops-center'));

	load_match(1);
};
