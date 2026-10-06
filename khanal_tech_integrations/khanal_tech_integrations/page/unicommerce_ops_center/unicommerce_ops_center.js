frappe.pages['unicommerce-ops-center'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Unicommerce Ops Center',
		single_column: true,
	});

	const API = 'khanal_tech_integrations.unicommerce.api.ops';
	const GUARDRAIL_FILTER_KEY = 'uc_ops_guardrail_filter';
	const CN_FILTER_KEY = 'uc_ops_cn_filter';
	const FAILURES_PAGE_SIZE_KEY = 'uc_ops_failures_page_size';
	const RETURNS_PAGE_SIZE_KEY = 'uc_ops_returns_page_size';
	const RECON_PAGE_SIZE_KEY = 'uc_ops_recon_page_size';
	const BATCH_PAGE_SIZE_KEY = 'uc_ops_batch_page_size';
	const GST_PIVOT_PREFS_KEY = 'uc_ops_gst_pivot_prefs';
	const IS_ADMIN = Boolean(frappe.user && (frappe.user.has_role('System Manager') || frappe.user.has_role('Administrator')));
	let CURRENT_CN_FILTER = 'all';
	const UI = {
		blue: '#2563eb',
		green: '#16a34a',
		amber: '#d97706',
		red: '#dc2626',
		purple: '#7c3aed',
		slate: '#64748b',
		surface: '#ffffff',
		border: '#e2e8f0',
	};
	const MONITOR_STATE = {
		counts: null,
		returns: null,
		failures: null,
		recon: null,
		guardrails: null,
	};
	let FAILURES_PAGE = 1;
	let FAILURES_PAGE_SIZE = 25;
	let RETURNS_PAGE = 1;
	let RETURNS_PAGE_SIZE = 20;
	let RECON_GAPS_PAGE = 1;
	let RECON_GRN_PAGE = 1;
	let RECON_INV_PAGE = 1;
	let GST_SIDE_BY_SIDE_PAGE = 1;
	let RECON_PAGE_SIZE = 20;
	let BATCH_PAGE = 1;
	let BATCH_PAGE_SIZE = 20;
	const GST_PIVOT_STATE = {
		uc: { sort_by: 'Taxable Value', top_n: 0 },
		sap: { sort_by: 'Taxable Value', top_n: 0, series_values: [] },
	};
	const REQUEST_LOCKS = {};
	let GST_RECON_POLL_TIMER = null;

	// ─── Helpers ─────────────────────────────────────────────────────────────

	function esc(v) {
		const s = String(v === undefined || v === null ? '' : v);
		return frappe.utils && frappe.utils.escape_html ? frappe.utils.escape_html(s)
			: s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
	}

	function acquire_request_lock(key) {
		if (REQUEST_LOCKS[key]) return false;
		REQUEST_LOCKS[key] = true;
		return true;
	}

	function release_request_lock(key) {
		REQUEST_LOCKS[key] = false;
	}

	function stop_gst_recon_poll() {
		if (GST_RECON_POLL_TIMER) {
			clearTimeout(GST_RECON_POLL_TIMER);
			GST_RECON_POLL_TIMER = null;
		}
	}

	function schedule_gst_recon_poll() {
		stop_gst_recon_poll();
		GST_RECON_POLL_TIMER = setTimeout(function () {
			load_gst_recon_status();
		}, 10000);
	}

	function iso_date(d) {
		const y = d.getFullYear();
		const m = String(d.getMonth() + 1).padStart(2, '0');
		const day = String(d.getDate()).padStart(2, '0');
		return `${y}-${m}-${day}`;
	}

	function parse_iso_date(value) {
		const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || '').trim());
		if (!m) return null;
		return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
	}

	function shift_days(date, delta) {
		const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
		d.setDate(d.getDate() + Number(delta || 0));
		return d;
	}

	function make_window(start, end) {
		return { start_date: iso_date(start), end_date: iso_date(end) };
	}

	function today_window() {
		const now = new Date();
		return make_window(now, now);
	}

	function yesterday_window() {
		const day = shift_days(new Date(), -1);
		return make_window(day, day);
	}

	function trailing_days_window(days) {
		const span = Math.max(Number(days || 1), 1);
		const end = new Date();
		return make_window(shift_days(end, -(span - 1)), end);
	}

	function current_month_window() {
		const now = new Date();
		return make_window(
			new Date(now.getFullYear(), now.getMonth(), 1),
			new Date(now.getFullYear(), now.getMonth() + 1, 0)
		);
	}

	function fiscal_year_window(offsetYears) {
		const now = new Date();
		const currentFyStartYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
		const startYear = currentFyStartYear + Number(offsetYears || 0);
		return make_window(
			new Date(startYear, 3, 1),
			new Date(startYear + 1, 3, 0)
		);
	}

	function dynamic_date_presets() {
		return [
			{ key: 'today', label: 'Today', ...today_window() },
			{ key: 'yesterday', label: 'Yesterday', ...yesterday_window() },
			{ key: 'last7', label: 'Last 7 Days', ...trailing_days_window(7) },
			{ key: 'thisMonth', label: 'This Month', ...current_month_window() },
			{ key: 'prevMonth', label: 'Previous Month', ...previous_month_window() },
			{ key: 'thisFY', label: 'This FY', ...fiscal_year_window(0) },
			{ key: 'prevFY', label: 'Previous FY', ...fiscal_year_window(-1) },
		];
	}

	function inclusive_day_count(start, end) {
		const s = parse_iso_date(start);
		const e = parse_iso_date(end);
		if (!s || !e) return 0;
		return Math.max(0, Math.round((e.getTime() - s.getTime()) / 86400000) + 1);
	}

	function format_short_date(value) {
		const d = parse_iso_date(value);
		return d
			? d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
			: (value || '—');
	}

	function format_window_label(start, end) {
		const days = inclusive_day_count(start, end);
		const span = days > 0 ? ` (${fmt(days)} day${days === 1 ? '' : 's'})` : '';
		return `${format_short_date(start)} → ${format_short_date(end)}${span}`;
	}

	// Always force the operator to pick start + end dates before triggering GST
	// reconciliation or invoice/credit-note posting. The dialog defaults to the
	// previous calendar month so the most common case is one click.
	function previous_month_window() {
		const now = new Date();
		const startOfThis = new Date(now.getFullYear(), now.getMonth(), 1);
		const lastDayPrev = new Date(startOfThis.getTime() - 86400000);
		const startPrev = new Date(lastDayPrev.getFullYear(), lastDayPrev.getMonth(), 1);
		return { start_date: iso_date(startPrev), end_date: iso_date(lastDayPrev) };
	}

	function prompt_date_range(opts, on_pick) {
		const defaults = previous_month_window();
		const presetMarkup = dynamic_date_presets().map(p => `
			<button type="button"
				class="btn btn-default btn-xs"
				data-range-preset="${esc(p.key)}"
				style="margin:0 6px 6px 0;">
				${esc(p.label)}
			</button>
		`).join('');
		const fields = [
			{
				fieldtype: 'HTML',
				fieldname: 'date_range_intro',
				options: `<div style="font-size:12px;color:#475569;margin-bottom:6px;">${frappe.utils.escape_html(opts.intro || 'Pick the start and end dates for this run. Both bounds are inclusive.')}</div>`,
			},
			{ fieldtype: 'Date', fieldname: 'start_date', label: 'Start date', reqd: 1, default: defaults.start_date },
			{ fieldtype: 'Column Break' },
			{ fieldtype: 'Date', fieldname: 'end_date', label: 'End date', reqd: 1, default: defaults.end_date },
			{ fieldtype: 'Section Break' },
			{
				fieldtype: 'HTML',
				fieldname: 'date_range_presets',
				options: `<div style="margin-top:8px;">
					<div style="font-size:11px;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em;">Quick presets</div>
					<div>${presetMarkup}</div>
				</div>`,
			},
		];
		if (opts.show_preview) {
			// Live preview of orders in the selected window, so the operator
			// knows exactly what's actionable before clicking the primary
			// button (and can explain any "missing" orders afterwards).
			fields.push(
				{ fieldtype: 'Section Break' },
				{
					fieldtype: 'HTML',
					fieldname: 'orders_preview',
					options: `<div id="uc-orders-preview" style="font-size:12px;color:#475569;padding:10px 12px;border:1px dashed #cbd5e1;border-radius:6px;background:#f8fafc;">
						<span style="color:#64748b;">Pick a date range to preview what will be posted.</span>
					</div>`,
				},
			);
		}
		if (opts.include_posting_controls) {
			fields.push(
				{ fieldtype: 'Section Break' },
				{
					fieldtype: 'HTML',
					fieldname: 'posting_tuning_note',
					options: `<div style="font-size:11.5px;color:#64748b;margin-bottom:6px;">
						Use <strong>Post All</strong> to drain large queues (2,000+ orders). Each pass posts up to the limit, then loops until all are done or the runtime cap is reached.
					</div>`,
				},
				{
					fieldtype: 'Int',
					fieldname: 'per_pass_limit',
					label: 'Orders per pass',
					reqd: 1,
					default: 500,
					description: 'Orders posted per pass. 500 is a good default — increase if SAP is fast, reduce if you see timeouts.',
				},
				{
					fieldtype: 'Int',
					fieldname: 'max_passes',
					label: 'Max passes',
					reqd: 1,
					default: 20,
					description: 'Auto-stop when queue is drained or this pass cap is reached.',
				},
				{
					fieldtype: 'Int',
					fieldname: 'max_runtime_mins',
					label: 'Max runtime (minutes)',
					reqd: 1,
					default: 60,
					description: 'Hard stop after this many minutes regardless of progress.',
				},
			);
		}
		if (opts.ask_posted_only) {
			fields.push(
				{ fieldtype: 'Section Break' },
				{
					fieldtype: 'Select',
					fieldname: 'compare_mode',
					label: 'Reconciliation mode',
					options: 'Finance Month (DocDate strict)\nOrder-ID Trace (date-agnostic)',
					default: 'Finance Month (DocDate strict)',
					description: 'finance_month = SAP DocDate strict (finance closing). order_id_trace = reconcile by UC order IDs across month boundaries.',
				},
				{
					fieldtype: 'Check',
					fieldname: 'posted_only',
					label: 'Check posted-to-SAP orders only',
					default: 1,
					description: 'When checked, the per-order comparison is restricted to orders that were successfully posted from Unicommerce to SAP (pipeline_status = posted). All other orders are excluded from the diff.',
				},
			);
		}
		if (opts.ask_email) {
			// For long-running jobs the user typically leaves the Desk; an
			// optional email address lets the backend fire-and-forget a
			// summary email (with xlsx attached) on success. Leaving it
			// blank keeps things silent and relies on the UI for polling.
			fields.push(
				{ fieldtype: 'Section Break' },
				{
					fieldtype: 'Data',
					fieldname: 'email_to',
					label: 'Email me the report when done (optional)',
					options: 'Email',
					default: (frappe.session && (frappe.session.user_email || frappe.session.user)) || '',
					description: 'The summary xlsx will be attached. Leave blank to skip; the workbook is still downloadable from the Ops Center.',
				},
			);
		}
		const dialog = new frappe.ui.Dialog({
			title: opts.title || 'Select date range',
			fields,
			primary_action_label: opts.primary_action_label || 'Run',
			primary_action: function (values) {
				if (!values.start_date || !values.end_date) {
					frappe.msgprint('Please select both start and end dates.');
					return;
				}
				if (values.start_date > values.end_date) {
					frappe.msgprint('Start date must be on or before end date.');
					return;
				}
				const email_to = (values.email_to || '').trim();
				if (opts.ask_email && email_to && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email_to)) {
					frappe.msgprint('Please enter a valid email address or leave the field blank.');
					return;
				}
				dialog.hide();
				const modeRaw = String(values.compare_mode || 'Finance Month (DocDate strict)');
				const compare_mode = modeRaw.toLowerCase().includes('order-id') ? 'order_id_trace' : 'finance_month';
				on_pick({
					start_date: values.start_date,
					end_date: values.end_date,
					email_to: email_to || null,
					posted_only: values.posted_only ? true : false,
					compare_mode: compare_mode,
					per_pass_limit: values.per_pass_limit,
					max_passes: values.max_passes,
					max_runtime_mins: values.max_runtime_mins,
				});
			},
		});
		dialog.show();
		$(dialog.$wrapper).find('[data-range-preset]').off('click').on('click', function () {
			const presetKey = String($(this).data('range-preset') || '');
			const hit = dynamic_date_presets().find(p => p.key === presetKey);
			if (!hit) return;
			dialog.set_value('start_date', hit.start_date);
			dialog.set_value('end_date', hit.end_date);
			['start_date', 'end_date'].forEach(function (fieldname) {
				const fld = dialog.get_field(fieldname);
				if (fld && fld.df && typeof fld.df.change === 'function') fld.df.change();
			});
		});

		if (opts.show_preview) {
			_wire_orders_preview(dialog);
		}
	}

	let _orders_preview_seq = 0;
	let _orders_preview_timer = null;

	function _orders_preview_markup(d) {
		if (!d || d.empty) {
			const msg = (d && d.message) || 'No orders found in this window.';
			return `<span style="color:#64748b;">${esc(msg)}</span>`;
		}
		const p = d.pipeline_status || {};
		const uw = d.uniware_status || {};
		const chip = (label, val, bg, fg) => `
			<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;background:${bg};color:${fg};font-size:11px;font-weight:600;margin:2px 4px 2px 0;">
				<span>${esc(label)}</span><span style="font-variant-numeric:tabular-nums;">${fmt(val || 0)}</span>
			</span>`;
		const pipeline_chips = [
			{ k: 'ready',      l: 'Ready',       bg: '#dcfce7', fg: '#166534' },
			{ k: 'batch_hold', l: 'Batch Hold',  bg: '#fef3c7', fg: '#92400e' },
			{ k: 'failed',     l: 'Failed',      bg: '#fee2e2', fg: '#991b1b' },
			{ k: 'fetched',    l: 'Fetched',     bg: '#e0f2fe', fg: '#075985' },
			{ k: 'pending',    l: 'Pending',     bg: '#f1f5f9', fg: '#475569' },
			{ k: 'posting',    l: 'Posting',     bg: '#ede9fe', fg: '#5b21b6' },
			{ k: 'verify',     l: 'Verify',      bg: '#ede9fe', fg: '#5b21b6' },
			{ k: 'posted',     l: 'Posted',      bg: '#dbeafe', fg: '#1e40af' },
			{ k: 'dead',       l: 'Dead',        bg: '#1f2937', fg: '#f9fafb' },
		].filter(c => (p[c.k] || 0) > 0).map(c => chip(c.l, p[c.k], c.bg, c.fg)).join('');

		const uw_entries = Object.entries(uw).slice(0, 4);
		const uw_chips = uw_entries.map(([k, v]) => chip(k, v, '#f1f5f9', '#334155')).join('');

		const actionable = Number(d.actionable_now || 0);
		const cooldown = Number(d.in_cooldown || 0);
		const posted = Number(d.posted_count || 0);
		const total = Number(d.total || 0);
		const action_color = actionable > 0 ? '#16a34a' : '#6b7280';

		return `
			<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
				<div><strong style="font-size:14px;">${fmt(total)}</strong> <span style="color:#64748b;">orders in window</span></div>
				<div style="color:${action_color};"><strong>${fmt(actionable)}</strong> actionable now</div>
				<div style="color:#b45309;"><strong>${fmt(cooldown)}</strong> in cooldown</div>
				<div style="color:#1e40af;"><strong>${fmt(posted)}</strong> already posted</div>
			</div>
			<div style="margin-bottom:6px;">
				<span style="color:#64748b;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;">Pipeline</span><br>
				${pipeline_chips || '<span style="color:#94a3b8;">—</span>'}
			</div>
			${uw_chips ? `<div>
				<span style="color:#64748b;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;">Uniware status</span><br>
				${uw_chips}
			</div>` : ''}
			<div style="margin-top:6px;font-size:10.5px;color:#94a3b8;">
				"Actionable now" = Ready + Batch Hold / Failed past cooldown. "In cooldown" rows will become actionable on future cycles.
			</div>
		`;
	}

	function _wire_orders_preview(dialog) {
		const fetch_preview = () => {
			const vals = dialog.get_values(true) || {};
			const from_date = vals.start_date;
			const to_date = vals.end_date;
			const $box = $(dialog.$wrapper).find('#uc-orders-preview');
			if (!from_date || !to_date) {
				$box.html('<span style="color:#64748b;">Pick both start and end dates to preview.</span>');
				return;
			}
			if (from_date > to_date) {
				$box.html('<span style="color:#b91c1c;">Start date must be on or before end date.</span>');
				return;
			}
			$box.html('<span style="color:#64748b;">Loading preview…</span>');
			const seq = ++_orders_preview_seq;
			frappe.call({
				method: API + '.ops_orders_in_date_range',
				args: { from_date, to_date },
				freeze: false,
				callback: function (r) {
					if (seq !== _orders_preview_seq) return; // a newer request is in flight
					$box.html(_orders_preview_markup(r && r.message));
				},
				error: function () {
					if (seq !== _orders_preview_seq) return;
					$box.html('<span style="color:#b91c1c;">Preview failed — check Error Log.</span>');
				},
			});
		};
		const debounced = () => {
			if (_orders_preview_timer) clearTimeout(_orders_preview_timer);
			_orders_preview_timer = setTimeout(fetch_preview, 250);
		};
		['start_date', 'end_date'].forEach(fn => {
			const fld = dialog.get_field(fn);
			if (fld && fld.df) fld.df.change = debounced;
		});
		fetch_preview();
	}

	function fmt(v) {
		const n = Number(v || 0);
		return Number.isFinite(n) ? n.toLocaleString('en-IN') : '0';
	}

	function money(v) {
		const n = Number(v || 0);
		return Number.isFinite(n) ? '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '₹0.00';
	}

	function pct(part, total) {
		return total > 0 ? Math.round((part / total) * 100) : 0;
	}

	function num(v) {
		const n = Number(v || 0);
		return Number.isFinite(n) ? n : 0;
	}

	function stat_card(title, id, color) {
		return `<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:140px;flex:1;">
			<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">${title}</div>
			<div id="${id}" style="font-size:26px;font-weight:700;color:${color || '#212529'};margin-top:4px;">-</div>
		</div>`;
	}

	function status_pill(status) {
		const map = {
			posted:'#d4edda,#155724', synced:'#d4edda,#155724', complete:'#d4edda,#155724',
			failed:'#f8d7da,#721c24', dead:'#f5c6cb,#491217',
			posting:'#fff3cd,#856404', verify:'#d1ecf1,#0c5460',
			ready:'#cce5ff,#004085', fetched:'#e2e3e5,#383d41',
			pending:'#e2e3e5,#383d41', batch_hold:'#e2d9f3,#432874',
			partial:'#fff3cd,#856404',
		};
		const s = (status || '').toLowerCase();
		const [bg, col] = (map[s] || '#e2e3e5,#383d41').split(',');
		return `<span style="background:${bg};color:${col};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;text-transform:capitalize;white-space:nowrap;">${esc(status)}</span>`;
	}

	function stage_badge(stage) {
		const bg = { orders:'#cce5ff', credit_notes:'#e2d9f3', inventory:'#fff3cd' }[stage] || '#e2e3e5';
		return `<span style="background:${bg};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">${esc(stage.replace(/_/g,' '))}</span>`;
	}

	function progress_row(label, value, total, color) {
		const pct_v = total > 0 ? Math.min(100, Math.round((Number(value || 0) / Number(total || 1)) * 100)) : 0;
		return `<div style="margin-bottom:8px;">
			<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
				<span style="font-size:11px;color:#6c757d;">${esc(label)}</span>
				<span style="font-size:11px;font-weight:700;color:#212529;">${fmt(value)} <span style="color:#6c757d;font-weight:500;">(${pct_v}%)</span></span>
			</div>
			<div style="height:8px;background:#eef2f6;border-radius:5px;overflow:hidden;">
				<div style="height:100%;width:${pct_v}%;background:${color};border-radius:5px;"></div>
			</div>
		</div>`;
	}

	function trend_chip(label, value, tone) {
		const tone_map = {
			good: { bg: '#dcfce7', fg: UI.green },
			warn: { bg: '#fef3c7', fg: UI.amber },
			bad: { bg: '#fee2e2', fg: UI.red },
			info: { bg: '#dbeafe', fg: UI.blue },
		};
		const t = tone_map[tone] || tone_map.info;
		return `<span style="display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;background:${t.bg};color:${t.fg};font-size:11px;font-weight:700;">
			${esc(label)}: ${esc(value)}
		</span>`;
	}

	function page_size_selector(id, current) {
		const opts = [10, 20, 50, 100];
		return `<label style="display:inline-flex;align-items:center;gap:6px;font-size:12px;color:#64748b;">
			Rows
			<select id="${id}" class="form-control form-control-sm" style="width:78px;height:28px;padding:2px 6px;font-size:12px;">
				${opts.map(v => `<option value="${v}" ${Number(current) === v ? 'selected' : ''}>${v}</option>`).join('')}
			</select>
		</label>`;
	}

	function doctype_route(doctype) {
		const map = {
			'UC Credit Note Staging': 'uc-credit-note-staging',
			'SAP Inventory Transfers': 'sap-inventory-transfers',
			'Unicommerce Orders': 'unicommerce-orders',
		};
		return map[doctype] || String(doctype || '').toLowerCase().replace(/ /g, '-');
	}

	const ORDER_COLOR = { fetched:'#adb5bd',pending:'#adb5bd',batch_hold:'#9b59b6',ready:'#0d6efd',posting:'#fd7e14',verify:'#17a2b8',posted:'#28a745',failed:'#dc3545',dead:'#7f0000' };
	const CN_COLOR    = { pending:'#adb5bd',posting:'#fd7e14',posted:'#28a745',failed:'#dc3545',dead:'#7f0000' };
	const INV_COLOR   = { Pending:'#adb5bd',Synced:'#28a745',Failed:'#dc3545',Partial:'#fd7e14' };
	const STATUS_ORD  = ['dead','failed','partial','batch_hold','posting','verify','ready','fetched','pending','posted','Synced','Pending','Failed','Partial'];

	function pipeline_bars(counts, color_map) {
		const total = counts._total || 0;
		const rows = Object.entries(counts).filter(([k]) => k !== '_total' && counts[k] > 0)
			.sort(([a],[b]) => (STATUS_ORD.indexOf(a)+1||99) - (STATUS_ORD.indexOf(b)+1||99));
		if (!rows.length) return '<div style="color:#6c757d;font-size:12px;">No records</div>';
		return rows.map(([status, count]) => {
			const w = total > 0 ? Math.max(Math.round((count/total)*100), 2) : 0;
			const c = color_map[status] || '#adb5bd';
			return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
				<div style="width:74px;font-size:11px;color:#6c757d;text-transform:capitalize;flex-shrink:0;">${esc(status)}</div>
				<div style="flex:1;height:6px;background:#f3f4f6;border-radius:3px;overflow:hidden;">
					<div style="width:${w}%;height:100%;background:${c};border-radius:3px;"></div>
				</div>
				<div style="width:40px;text-align:right;font-size:12px;font-weight:600;color:#212529;">${fmt(count)}</div>
			</div>`;
		}).join('');
	}

	function log(container, message, type) {
		const colors = { info:'#adb5bd', success:'#28a745', error:'#f87171', warning:'#fbbf24', divider:'#555', endpoint:'#60a5fa' };
		const prefix = { info:'>', success:'OK', error:'ERR', warning:'WARN', divider:'-', endpoint:'API' };
		const color  = colors[type] || colors.info;
		const icon   = prefix[type] || '>';
		const time   = new Date().toLocaleTimeString();
		if (type === 'divider') {
			container.append('<div style="border-top:1px solid #444;margin:6px 0;"></div>');
		} else {
			container.append(
				`<div style="margin:2px 0;font-size:12px;">
					<span style="color:#6b7280;margin-right:6px;">${time}</span>
					<span style="color:${color};display:inline-block;min-width:34px;">${icon}</span>
					<span style="color:${color};">${esc(message)}</span>
				</div>`
			);
		}
		container.scrollTop(container[0].scrollHeight);
	}

	function log_result(container, worker, res) {
		log(container, '', 'divider');
		if (!res.ok) {
			log(container, `Error: ${res.error}`, 'error');
			return;
		}
		if (res.queued) {
			log(container, 'Job queued in the background — real-time progress shows in the stream above.', 'info');
			log(container, '', 'divider');
			return;
		}
		const r = res.result || {};
		if (worker === 'fetch_orders') {
			if (r.explicit_range) {
				log(container, `Mode: Date range  ${esc(r.since)} → ${esc(r.to)}  (cursor NOT advanced)`, 'warning');
			} else {
				log(container, `Mode: Cursor  since ${esc(r.since)}`, 'info');
			}
			(r.endpoints_used || []).forEach(ep => log(container, `API: POST /${ep}`, 'endpoint'));
			log(container, `Fetched from UC: ${fmt(r.fetched)} orders`, 'info');
			log(container, `New staged: ${fmt(r.new)}`, 'success');
			log(container, `Updated existing: ${fmt(r.updated)}`, 'info');
			if (r.skipped_posted)  log(container, `Skipped (already posted): ${fmt(r.skipped_posted)}`, 'info');
			if (r.detail_failed)   log(container, `Detail fetch failed: ${fmt(r.detail_failed)}`, 'warning');
			if (!r.explicit_range && r.next_cursor) log(container, `Next cursor saved: ${esc(r.next_cursor)}`, 'info');
		} else if (worker === 'promote_fetched_to_ready') {
			log(container, `Moved to ready: ${fmt(r.moved_to_ready)}`, 'success');
			if (r.deferred) log(container, `Deferred (not eligible yet): ${fmt(r.deferred)}`, 'warning');
		} else if (worker === 'fetch_returns') {
			if (r.explicit_range) {
				log(container, `Mode: Date range  ${esc(r.since)} → ${esc(r.to)}  (cursor NOT advanced)`, 'warning');
			} else {
				log(container, `Mode: Cursor  since ${esc(r.since)}`, 'info');
			}
			(r.endpoints_used || []).forEach(ep => log(container, `API: POST /${ep}`, 'endpoint'));
			log(container, `Fetched from UC: ${fmt(r.fetched)} returns`, 'info');
			log(container, `Credit notes staged: ${fmt(r.created)}`, 'success');
			if (r.updated)                   log(container, `Updated existing: ${fmt(r.updated)}`, 'info');
			if (r.skipped_existing)          log(container, `Skipped (already posted): ${fmt(r.skipped_existing)}`, 'info');
			if (r.skipped_parent_not_found)  log(container, `Skipped — parent order not yet staged: ${fmt(r.skipped_parent_not_found)}  (fetch orders for this date range first)`, 'warning');
			if (r.skipped_no_ids)            log(container, `Skipped (no order/return ID — likely RTO): ${fmt(r.skipped_no_ids)}`, 'warning');
			if (!r.explicit_range && r.next_cursor) log(container, `Next cursor saved: ${esc(r.next_cursor)}`, 'info');
		} else if (worker === 'post_invoices') {
			if (r.promoted_to_ready)    log(container, `Auto-promoted fetched → ready: ${fmt(r.promoted_to_ready)}`, 'info');
			if (r.recovered_failed)     log(container, `Failed orders recovered for retry: ${fmt(r.recovered_failed)}`, 'info');
			if (r.recovered_batch_hold) log(container, `Batch hold orders re-queued (cooldown expired): ${fmt(r.recovered_batch_hold)}`, 'info');
			if (r.escalated_batch_hold) log(container, `Batch hold escalated to dead (cap exceeded): ${fmt(r.escalated_batch_hold)}`, 'error');
			log(container, `Ready orders processed: ${fmt(r.ready_processed)}`, 'info');
			log(container, `Posted to SAP: ${fmt(r.ready_posted)}`, 'success');
			if (r.ready_batch_hold) log(container, `Moved to batch hold: ${fmt(r.ready_batch_hold)}`, 'warning');
			if (r.ready_failed)     log(container, `Failed: ${fmt(r.ready_failed)}`, 'error');
			if (r.verify_checked)   log(container, `Verify queue checked: ${fmt(r.verify_checked)}, confirmed: ${fmt(r.verify_posted)}, requeued: ${fmt(r.verify_requeued)}, dead: ${fmt(r.verify_dead)}`, 'info');
		} else if (worker === 'post_credit_notes') {
			log(container, `Processed: ${fmt(r.processed)}`, 'info');
			log(container, `Posted to SAP: ${fmt(r.posted)}`, 'success');
			if (r.deferred) log(container, `Deferred (parent not posted): ${fmt(r.deferred)}`, 'warning');
			if (r.failed)   log(container, `Failed: ${fmt(r.failed)}`, 'error');
			if (r.dead)     log(container, `Dead: ${fmt(r.dead)}`, 'error');
		} else if (worker === 'retry_batch_holds') {
			log(container, `Released from batch hold → ready: ${fmt(r.moved_to_ready)}`, 'success');
		} else {
			log(container, JSON.stringify(r), 'info');
		}
		log(container, '', 'divider');
		log(container, 'Done. Refreshing dashboard…', 'success');
	}

	function run_worker(worker, $btn, $log) {
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Running…');
		$log.show();
		log($log, `Starting ${worker.replace(/_/g,' ')}…`, 'info');

		frappe.call({
			method: API + '.ops_run_worker',
			args: { worker },
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				if (r.message) {
					log_result($log, worker, r.message);
					if (r.message.ok) {
						frappe.show_alert({ message: `${worker.replace(/_/g,' ')} completed`, indicator: 'green' }, 5);
						load_dashboard();
					} else {
						frappe.show_alert({ message: `${worker.replace(/_/g,' ')} failed`, indicator: 'red' }, 6);
					}
				}
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				log($log, 'Request failed — check error log', 'error');
			},
		});
	}

	// ─── Page HTML ─────────────────────────────────────────────────────────────

	$(wrapper).find('.page-content').html(`
<style>
	/* ═══ Design tokens ═══════════════════════════════════════════════════════ */
	#uc-ops-root {
		--bg: #ffffff;
		--surface: #ffffff;
		--surface-muted: #f8fafc;
		--surface-hover: #f1f5f9;
		--border: #e2e8f0;
		--border-strong: #cbd5e1;
		--text: #0f172a;
		--text-muted: #64748b;
		--text-subtle: #94a3b8;
		--accent: #2563eb;
		--accent-hover: #1d4ed8;
		--accent-soft: #eff6ff;
		--ok: #16a34a;
		--ok-soft: #dcfce7;
		--warn: #d97706;
		--warn-soft: #fef3c7;
		--bad: #dc2626;
		--bad-soft: #fee2e2;
		--idle: #94a3b8;
		--idle-soft: #f1f5f9;
		--radius: 10px;
		--radius-sm: 8px;
		--shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
		--shadow-md: 0 4px 12px rgba(15, 23, 42, 0.06);
		--gap-sm: 12px;
		--gap: 16px;
		--gap-lg: 24px;
		max-width: 1200px;
		margin: 20px auto 56px;
		font-family: inherit;
		color: var(--text);
	}
	#uc-ops-root * { box-sizing: border-box; }
	#uc-ops-root .btn { border-radius: var(--radius-sm); font-weight: 600; }
	#uc-ops-root .btn.btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
	#uc-ops-root .btn.btn-primary:hover, #uc-ops-root .btn.btn-primary:focus { background: var(--accent-hover); border-color: var(--accent-hover); color: #fff; }

	/* Header */
	#uc-ops-root .uc-app-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: var(--gap);
		flex-wrap: wrap;
		margin-bottom: var(--gap-lg);
		padding-bottom: var(--gap);
		border-bottom: 1px solid var(--border);
	}
	#uc-ops-root .uc-app-title { margin: 0; font-size: 22px; font-weight: 700; letter-spacing: -0.01em; color: var(--text); }
	#uc-ops-root .uc-app-subtitle { margin: 6px 0 0; font-size: 13px; color: var(--text-muted); }
	#uc-ops-root .uc-header-actions { display: flex; gap: 8px; flex-wrap: wrap; }

	/* Hero metric strip */
	#uc-ops-root .uc-hero-grid {
		display: grid;
		grid-template-columns: repeat(6, 1fr);
		gap: var(--gap-sm);
		margin-bottom: var(--gap-lg);
	}
	@media (max-width: 1000px) { #uc-ops-root .uc-hero-grid { grid-template-columns: repeat(3, 1fr); } }
	@media (max-width: 600px)  { #uc-ops-root .uc-hero-grid { grid-template-columns: repeat(2, 1fr); } }
	#uc-ops-root .uc-hero-tile {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 14px 16px;
		box-shadow: var(--shadow-sm);
		transition: border-color .15s ease, box-shadow .15s ease;
		min-height: 82px;
	}
	#uc-ops-root .uc-hero-tile:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }
	#uc-ops-root .uc-hero-tile .label {
		font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
		color: var(--text-muted); font-weight: 600;
	}
	#uc-ops-root .uc-hero-tile .value {
		font-size: 28px; font-weight: 700; color: var(--text);
		margin-top: 6px; line-height: 1;
	}
	#uc-ops-root .uc-hero-tile .value .unit {
		font-size: 13px; color: var(--text-muted); font-weight: 500; margin-left: 6px;
	}
	#uc-ops-root .uc-hero-tile.accent .value { color: var(--accent); }
	#uc-ops-root .uc-hero-tile.warn .value { color: var(--warn); }
	#uc-ops-root .uc-hero-tile.bad .value { color: var(--bad); }
	#uc-ops-root .uc-hero-tile.ok .value { color: var(--ok); }
	#uc-ops-root .uc-hero-tile.health-tile .value {
		font-size: 14px; line-height: 1.45; font-weight: 600;
	}
	#uc-ops-root .uc-dot {
		display: inline-block; width: 8px; height: 8px; border-radius: 50%;
		background: var(--idle); margin-right: 6px; vertical-align: middle;
	}
	#uc-ops-root .uc-dot.ok   { background: var(--ok); }
	#uc-ops-root .uc-dot.warn { background: var(--warn); }
	#uc-ops-root .uc-dot.bad  { background: var(--bad); }

	/* Wizard stepper */
	#uc-ops-root .uc-stepper {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		overflow: hidden;
		margin-bottom: var(--gap);
		box-shadow: var(--shadow-sm);
	}
	#uc-ops-root .uc-step-tab {
		display: flex; align-items: center; gap: 10px;
		padding: 14px 18px;
		background: var(--surface);
		cursor: pointer;
		border: none; border-right: 1px solid var(--border);
		text-align: left; font: inherit; color: var(--text-muted);
		position: relative;
		transition: background .15s ease, color .15s ease;
	}
	#uc-ops-root .uc-step-tab:last-child { border-right: 0; }
	#uc-ops-root .uc-step-tab:hover { background: var(--surface-muted); color: var(--text); }
	#uc-ops-root .uc-step-tab.active { color: var(--text); background: var(--accent-soft); }
	#uc-ops-root .uc-step-tab.active::after {
		content: ""; position: absolute; left: 0; right: 0; bottom: 0;
		height: 3px; background: var(--accent);
	}
	#uc-ops-root .uc-step-num {
		width: 28px; height: 28px; border-radius: 50%;
		display: inline-flex; align-items: center; justify-content: center;
		background: var(--idle-soft); color: var(--text-muted);
		font-size: 12px; font-weight: 700; flex-shrink: 0;
		transition: background .15s ease, color .15s ease;
	}
	#uc-ops-root .uc-step-tab.active .uc-step-num { background: var(--accent); color: #fff; }
	#uc-ops-root .uc-step-tab.done .uc-step-num  { background: var(--ok); color: #fff; }
	#uc-ops-root .uc-step-label { display: flex; flex-direction: column; min-width: 0; }
	#uc-ops-root .uc-step-title { font-size: 14px; font-weight: 600; }
	#uc-ops-root .uc-step-desc  { font-size: 12px; color: var(--text-subtle); font-weight: 400; margin-top: 1px; }
	@media (max-width: 1100px) {
		#uc-ops-root .uc-stepper { grid-template-columns: repeat(3, 1fr); }
		#uc-ops-root .uc-step-tab:nth-child(3) { border-right: 0; }
		#uc-ops-root .uc-step-tab:nth-child(1),
		#uc-ops-root .uc-step-tab:nth-child(2),
		#uc-ops-root .uc-step-tab:nth-child(3) { border-bottom: 1px solid var(--border); }
	}
	@media (max-width: 700px) {
		#uc-ops-root .uc-stepper { grid-template-columns: repeat(2, 1fr); }
		#uc-ops-root .uc-step-tab:nth-child(2) { border-right: 0; }
		#uc-ops-root .uc-step-tab:nth-child(odd):not(:last-child) { border-right: 1px solid var(--border); }
		#uc-ops-root .uc-step-tab { border-bottom: 1px solid var(--border); }
	}

	/* Step panels */
	#uc-ops-root .uc-step-panel {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		margin-bottom: var(--gap-lg);
		overflow: hidden;
		box-shadow: var(--shadow-sm);
	}
	#uc-ops-root .uc-step-panel[hidden] { display: none; }
	#uc-ops-root .uc-step-header {
		padding: 20px 24px;
		border-bottom: 1px solid var(--border);
		background: var(--surface-muted);
	}
	#uc-ops-root .uc-step-heading { margin: 0; font-size: 18px; font-weight: 700; letter-spacing: -0.005em; color: var(--text); }
	#uc-ops-root .uc-step-intro { margin: 6px 0 0; font-size: 13px; color: var(--text-muted); line-height: 1.55; max-width: 780px; }
	#uc-ops-root .uc-step-body { padding: 22px 24px; }

	/* Sub-cards */
	#uc-ops-root .uc-sub {
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		padding: 16px 18px;
		background: var(--surface);
		margin-bottom: var(--gap);
	}
	#uc-ops-root .uc-sub:last-child { margin-bottom: 0; }
	#uc-ops-root .uc-sub-title {
		font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
		font-weight: 700; color: var(--text-muted); margin-bottom: 12px;
	}
	#uc-ops-root .uc-sub-row {
		display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;
	}
	#uc-ops-root .uc-field label {
		display: block; font-size: 11px; font-weight: 600;
		color: var(--text-muted); margin-bottom: 4px;
		text-transform: uppercase; letter-spacing: .04em;
	}
	#uc-ops-root .uc-field .form-control { font-size: 13px; width: 160px; }
	#uc-ops-root .uc-helptext { margin: 12px 0 0; font-size: 12px; color: var(--text-muted); line-height: 1.55; }
	#uc-ops-root .uc-helptext strong { color: var(--text); }

	/* Log console */
	#uc-ops-root .uc-log {
		background: #0f172a; color: #e2e8f0;
		border-radius: var(--radius-sm);
		padding: 12px 14px;
		min-height: 80px; max-height: 240px;
		overflow-y: auto;
		font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
		font-size: 12px; line-height: 1.6;
	}

	/* Next CTA */
	#uc-ops-root .uc-next-cta {
		margin-top: var(--gap);
		padding: 14px 18px;
		background: var(--accent-soft);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		display: flex; justify-content: space-between; align-items: center;
		gap: 12px; flex-wrap: wrap; font-size: 13px;
	}
	#uc-ops-root .uc-next-cta .cta-text { color: var(--text); }
	#uc-ops-root .uc-next-cta .cta-text strong { font-weight: 700; }

	/* Drawers */
	#uc-ops-root .uc-drawer {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		margin-bottom: var(--gap-sm);
		box-shadow: var(--shadow-sm);
		overflow: hidden;
	}
	#uc-ops-root .uc-drawer > summary {
		padding: 14px 18px;
		cursor: pointer;
		list-style: none;
		display: flex; align-items: center;
		font-size: 14px; font-weight: 600; color: var(--text);
	}
	#uc-ops-root .uc-drawer > summary::-webkit-details-marker { display: none; }
	#uc-ops-root .uc-drawer > summary::before {
		content: "›"; margin-right: 10px;
		color: var(--text-muted); font-size: 18px; font-weight: 700;
		transition: transform .15s ease;
		display: inline-block;
	}
	#uc-ops-root .uc-drawer[open] > summary::before { transform: rotate(90deg); }
	#uc-ops-root .uc-drawer > summary:hover { background: var(--surface-muted); }
	#uc-ops-root .uc-drawer-body { padding: 4px 18px 18px; border-top: 1px solid var(--border); }
	#uc-ops-root .uc-drawer-badge {
		margin-left: auto;
		background: var(--idle-soft); color: var(--text-muted);
		padding: 3px 10px; border-radius: 999px;
		font-size: 11px; font-weight: 600;
	}
	#uc-ops-root .uc-drawer-badge.has-work { background: var(--bad-soft); color: var(--bad); }

	/* Tables */
	#uc-ops-root .table { margin-bottom: 0; }
	#uc-ops-root .table thead th {
		background: var(--surface-muted);
		color: var(--text-muted);
		font-size: 11px; text-transform: uppercase; letter-spacing: .03em;
		font-weight: 600;
		border-bottom: 1px solid var(--border);
		white-space: nowrap;
	}
	#uc-ops-root .table tbody td { vertical-align: middle; font-size: 12px; }
	#uc-ops-root .table tbody tr:hover { background: var(--accent-soft); }

	/* Section separators inside drawer */
	#uc-ops-root .uc-section-sep {
		margin: var(--gap-lg) 0 var(--gap);
		display: flex; align-items: center; gap: 10px;
		color: var(--text-subtle); font-size: 11px; font-weight: 700;
		text-transform: uppercase; letter-spacing: .06em;
	}
	#uc-ops-root .uc-section-sep::after {
		content: ""; flex: 1; height: 1px; background: var(--border);
	}

	/* GST reconciliation — reader guide + layout */
	#uc-ops-root .uc-gst-readme {
		margin-bottom: var(--gap);
		padding: 14px 16px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: linear-gradient(180deg, var(--surface-muted) 0%, var(--surface) 70%);
		box-shadow: var(--shadow-sm);
	}
	#uc-ops-root .uc-gst-readme-title {
		font-size: 12px; font-weight: 700; color: var(--text);
		margin-bottom: 8px; letter-spacing: 0.01em;
	}
	#uc-ops-root .uc-gst-readme-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 10px;
	}
	#uc-ops-root .uc-gst-readme-item {
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--surface);
		padding: 10px 12px;
	}
	#uc-ops-root .uc-gst-readme-kicker {
		font-size: 10.5px; text-transform: uppercase; letter-spacing: .06em;
		font-weight: 700; color: var(--text-muted); margin-bottom: 4px;
	}
	#uc-ops-root .uc-gst-readme-body {
		font-size: 12.5px; line-height: 1.5; color: var(--text);
	}
	#uc-ops-root .uc-gst-pivot-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
		gap: var(--gap);
		margin-bottom: var(--gap);
	}
	#uc-ops-root .uc-gst-pivot-title {
		font-size: 13px; font-weight: 700; margin-bottom: 8px; color: var(--text);
	}

	/* Chips */
	#uc-ops-root .uc-chip {
		display: inline-flex; align-items: center; gap: 6px;
		padding: 3px 10px; border-radius: 999px;
		font-size: 11px; font-weight: 600;
		background: var(--idle-soft); color: var(--text-muted);
		white-space: nowrap;
	}
	#uc-ops-root .uc-chip.ok     { background: var(--ok-soft); color: var(--ok); }
	#uc-ops-root .uc-chip.warn   { background: var(--warn-soft); color: var(--warn); }
	#uc-ops-root .uc-chip.bad    { background: var(--bad-soft); color: var(--bad); }
	#uc-ops-root .uc-chip.accent { background: var(--accent-soft); color: var(--accent); }

	/* Inner tabs (Step 4) */
	#uc-ops-root .uc-inner-tabs {
		display: flex; gap: 4px;
		border-bottom: 1px solid var(--border);
		margin-bottom: var(--gap);
	}
	#uc-ops-root .uc-inner-tab {
		border: none; background: transparent;
		padding: 10px 16px;
		font-size: 13px; font-weight: 600;
		color: var(--text-muted);
		cursor: pointer;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
	}
	#uc-ops-root .uc-inner-tab:hover { color: var(--text); }
	#uc-ops-root .uc-inner-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
	#uc-ops-root .uc-inner-pane[hidden] { display: none; }

	/* Misc compat */
	#uc-ops-root #dashboard-status,
	#uc-ops-root #guardrail-status,
	#uc-ops-root #analytics-status { color: var(--text-muted) !important; font-weight: 600; font-size: 12px; }
	#uc-ops-root .ops-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); }
	@media (max-width: 900px) { #uc-ops-root .ops-grid-2 { grid-template-columns: 1fr; } }
</style>

<div id="uc-ops-root">

	<!-- ═══ Header ═══════════════════════════════════════════════════════════ -->
	<header class="uc-app-header">
		<div>
			<h1 class="uc-app-title">Unicommerce → SAP B1</h1>
			<p class="uc-app-subtitle">Fetch · Validate · Post · Reconcile &nbsp;·&nbsp; <span id="dashboard-status">Loading…</span></p>
		</div>
		<div class="uc-header-actions">
			<button id="btn-refresh" class="btn btn-default btn-sm">Refresh</button>
			<button id="btn-test-conn" class="btn btn-default btn-sm">Test Connections</button>
			<button id="btn-inventory-match" class="btn btn-default btn-sm">Inventory Match</button>
			<button id="btn-settings" class="btn btn-default btn-sm">Settings</button>
		</div>
	</header>

	<!-- ═══ Hero metric strip ════════════════════════════════════════════════ -->
	<div class="uc-hero-grid">
		<div class="uc-hero-tile health-tile">
			<div class="label">Health</div>
			<div class="value">
				<div id="health-sap"><span class="uc-dot"></span>SAP…</div>
				<div id="health-uc"><span class="uc-dot"></span>UC…</div>
			</div>
		</div>
		<div class="uc-hero-tile">
			<div class="label">Fetched (All Dates)</div>
			<div class="value" id="hero-fetched">–</div>
		</div>
		<div class="uc-hero-tile accent">
			<div class="label">Ready (All Dates)</div>
			<div class="value" id="hero-ready">–</div>
		</div>
		<div class="uc-hero-tile warn">
			<div class="label">Batch Hold (All Dates)</div>
			<div class="value" id="hero-batch-hold">–</div>
		</div>
		<div class="uc-hero-tile bad">
			<div class="label">Failed (All Dates)</div>
			<div class="value" id="hero-failed">–</div>
		</div>
		<div class="uc-hero-tile">
			<div class="label">CN Waiting (All Dates)</div>
			<div class="value" id="hero-cn-ready">–</div>
		</div>
	</div>

	<!-- ═══ Wizard stepper ═══════════════════════════════════════════════════ -->
	<nav class="uc-stepper" role="tablist" aria-label="Posting workflow">
		<button class="uc-step-tab active" data-step="1" role="tab" aria-selected="true">
			<span class="uc-step-num">1</span>
			<span class="uc-step-label">
				<span class="uc-step-title">Fetch</span>
				<span class="uc-step-desc">Pull from Unicommerce</span>
			</span>
		</button>
		<button class="uc-step-tab" data-step="2" role="tab" aria-selected="false">
			<span class="uc-step-num">2</span>
			<span class="uc-step-label">
				<span class="uc-step-title">Validate</span>
				<span class="uc-step-desc">Check batch stock</span>
			</span>
		</button>
		<button class="uc-step-tab" data-step="3" role="tab" aria-selected="false">
			<span class="uc-step-num">3</span>
			<span class="uc-step-label">
				<span class="uc-step-title">Post</span>
				<span class="uc-step-desc">Push to SAP B1</span>
			</span>
		</button>
		<button class="uc-step-tab" data-step="4" role="tab" aria-selected="false">
			<span class="uc-step-num">4</span>
			<span class="uc-step-label">
				<span class="uc-step-title">Reconcile</span>
				<span class="uc-step-desc">GST &amp; gaps</span>
			</span>
		</button>
		<button class="uc-step-tab" data-step="5" role="tab" aria-selected="false">
			<span class="uc-step-num">5</span>
			<span class="uc-step-label">
				<span class="uc-step-title">Inward Inv</span>
				<span class="uc-step-desc">SAP → UC PO+GRN</span>
			</span>
		</button>
	</nav>

	<!-- ═══ Step 1 · Fetch ═══════════════════════════════════════════════════ -->
	<section class="uc-step-panel" data-step-panel="1">
		<div class="uc-step-header">
			<h2 class="uc-step-heading">Step 1 · Fetch from Unicommerce</h2>
			<p class="uc-step-intro">
				Pull new and updated orders and returns from the Unicommerce API and stage them locally.
				Leave both date fields blank to use the saved cursor (incremental), or pick a date range for a backfill — cursor is <em>not</em> advanced in date-range mode.
			</p>
		</div>
		<div class="uc-step-body">

			<div class="uc-sub">
				<div class="uc-sub-title">Fetch Orders</div>
				<div class="uc-sub-row">
					<div class="uc-field">
						<label>From Date</label>
						<input id="fetch-from-date" type="date" class="form-control form-control-sm">
					</div>
					<div class="uc-field">
						<label>To Date</label>
						<input id="fetch-to-date" type="date" class="form-control form-control-sm">
					</div>
					<button id="btn-fetch-orders" class="btn btn-primary btn-sm">Fetch Orders</button>
					<button id="btn-fetch-clear-dates" class="btn btn-default btn-xs" title="Clear dates and use cursor">Clear</button>
					<span id="fetch-mode-badge" class="uc-chip" style="align-self:center;">Mode: Cursor</span>
				</div>
			</div>

			<div class="uc-sub">
				<div class="uc-sub-title">Fetch Returns</div>
				<div class="uc-sub-row">
					<div class="uc-field">
						<label>From Date</label>
						<input id="returns-from-date" type="date" class="form-control form-control-sm">
					</div>
					<div class="uc-field">
						<label>To Date</label>
						<input id="returns-to-date" type="date" class="form-control form-control-sm">
					</div>
					<button id="btn-fetch-returns" class="btn btn-default btn-sm">Fetch Returns</button>
					<button id="btn-returns-clear-dates" class="btn btn-default btn-xs" title="Clear dates and use cursor">Clear</button>
					<span id="returns-mode-badge" class="uc-chip" style="align-self:center;">Mode: Cursor</span>
				</div>
			</div>

			<div class="uc-sub">
				<div class="uc-sub-title">Promote Fetched → Ready</div>
				<div class="uc-sub-row" style="align-items:center;">
					<div style="flex:1;min-width:220px;font-size:13px;color:var(--text-muted);line-height:1.5;">
						Validates eligibility (channel mapping, tax, batch info) and moves <em>fetched</em> orders to <em>ready</em>.
						Runs automatically at the start of every Post Invoices cycle.
					</div>
					<button id="btn-promote-ready" class="btn btn-default btn-sm">Promote → Ready</button>
				</div>
			</div>

			<div id="fetch-log" class="uc-log" style="display:none;"></div>

			<div class="uc-next-cta">
				<div class="cta-text">Fetch complete? <strong>Move to Step 2</strong> to pre-validate batch stock, or skip straight to Step 3.</div>
				<div style="display:flex;gap:8px;">
					<button type="button" class="btn btn-default btn-sm" data-goto-step="2">Next: Validate →</button>
					<button type="button" class="btn btn-primary btn-sm" data-goto-step="3">Skip to Post →</button>
				</div>
			</div>
		</div>
	</section>

	<!-- ═══ Step 2 · Validate ════════════════════════════════════════════════ -->
	<section class="uc-step-panel" data-step-panel="2" hidden>
		<div class="uc-step-header">
			<h2 class="uc-step-heading">Step 2 · Validate Batches (Live SAP)</h2>
			<p class="uc-step-intro">
				Optional but recommended before a big posting run. Pre-validate checks the stock currently available in SAP for every ready order and flags shortages before we try to post.
				Orders blocked on stock go to <em>batch_hold</em> status and are auto-retried every 30 minutes.
			</p>
		</div>
		<div class="uc-step-body">

			<div class="uc-sub">
				<div class="uc-sub-title">Batch Validation</div>
				<div class="uc-sub-row">
					<button id="btn-load-batch" class="btn btn-default btn-sm">Load Batch Status</button>
					<button id="btn-prevalidate-batches" class="btn btn-primary btn-sm">Pre-Validate Ready Orders</button>
					<button id="btn-retry-batch-holds" class="btn btn-default btn-sm">Release All Batch Holds</button>
					<button id="btn-fefo-toggle" class="btn btn-default btn-sm" style="margin-left:8px;" title="EC-FG FEFO Fallback: when enabled, orders whose UC-specified batch has insufficient stock in EC-FG will auto-allocate via FEFO instead of going to batch_hold">FEFO Fallback: …</button>
					<div style="display:flex;gap:6px;align-items:center;margin-left:auto;">
						<input id="batch-validate-input" type="text" class="form-control form-control-sm"
							placeholder="UC Order ID or record name" style="width:220px;font-size:12px;">
						<button id="btn-validate-order" class="btn btn-default btn-sm">Validate Order</button>
					</div>
				</div>
			</div>

			<div id="batch-summary" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:var(--gap);"></div>

			<div id="batch-shortage-digest" style="display:none;margin-bottom:var(--gap);border:1px solid var(--warn);border-radius:var(--radius-sm);overflow:hidden;">
				<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--warn-soft);border-bottom:1px solid var(--warn);flex-wrap:wrap;">
					<div style="font-size:13px;font-weight:700;color:var(--warn);">
						Shortage Digest — inventory action list
					</div>
					<div id="batch-digest-summary" style="font-size:12px;color:var(--text-muted);"></div>
					<div style="margin-left:auto;display:flex;gap:6px;">
						<button id="btn-digest-copy" class="btn btn-default btn-xs" title="Copy as tab-separated — paste into Excel / Google Sheets">Copy</button>
						<button id="btn-digest-csv" class="btn btn-default btn-xs" title="Download as CSV">Download CSV</button>
						<button id="btn-digest-create-gr" class="btn btn-warning btn-xs" title="Create one Goods Receipt in SAP B1 with all shorted items" style="display:none;">Create GR in SAP</button>
					</div>
				</div>
				<div style="overflow:auto;max-height:360px;">
					<table class="table table-bordered" style="margin:0;font-size:12px;min-width:900px;">
						<thead style="background:#fff;position:sticky;top:0;z-index:1;">
							<tr>
								<th>Warehouse</th>
								<th>Item Code</th>
								<th>Batch</th>
								<th style="text-align:right;">Qty Needed</th>
								<th style="text-align:right;">Qty Available</th>
								<th style="text-align:right;">Shortage</th>
								<th style="text-align:center;" title="EC-FG has enough stock across any batch — order will auto-recover via FEFO on next posting cycle">FEFO?</th>
								<th style="text-align:right;">Orders</th>
								<th>Affected Order IDs</th>
							</tr>
						</thead>
						<tbody id="batch-digest-tbody"></tbody>
					</table>
				</div>
			</div>

			<div id="batch-prevalidate-progress" style="display:none;margin-bottom:var(--gap);padding:12px 14px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-soft,#f8f9fb);">
				<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;">
					<div id="batch-prevalidate-progress-label" style="font-size:12px;font-weight:600;color:var(--text,#1f2937);">Starting pre-validate…</div>
					<div style="display:flex;gap:6px;align-items:center;">
						<span id="batch-prevalidate-progress-counter" style="font-size:11px;color:var(--muted,#6b7280);font-variant-numeric:tabular-nums;"></span>
						<button type="button" id="btn-prevalidate-cancel" class="btn btn-xs btn-default" style="font-size:11px;padding:2px 8px;">Cancel</button>
					</div>
				</div>
				<div style="background:var(--border,#e5e7eb);border-radius:999px;height:6px;overflow:hidden;">
					<div id="batch-prevalidate-progress-bar" style="height:100%;width:0;background:var(--accent,#2563eb);transition:width 300ms ease-out;"></div>
				</div>
				<div id="batch-prevalidate-progress-meta" style="display:flex;gap:14px;flex-wrap:wrap;font-size:11px;color:var(--muted,#6b7280);margin-top:8px;font-variant-numeric:tabular-nums;"></div>
			</div>

			<div id="batch-prevalidate-result" style="display:none;margin-bottom:var(--gap);padding:10px 14px;border-radius:var(--radius-sm);font-size:12px;"></div>

			<div id="batch-table-wrap" style="overflow:auto;max-height:420px;display:none;border:1px solid var(--border);border-radius:var(--radius-sm);">
				<table class="table table-bordered" style="margin:0;font-size:12px;min-width:760px;">
					<thead>
						<tr>
							<th>Order ID</th><th>Channel</th><th>Order Date</th>
							<th>In Hold</th><th>Attempts</th><th>Last Error</th><th>Actions</th>
						</tr>
					</thead>
					<tbody id="batch-tbody"></tbody>
				</table>
				<div id="batch-pagination" style="display:flex;justify-content:flex-end;align-items:center;gap:8px;padding:10px 12px;"></div>
			</div>

			<div class="uc-next-cta">
				<div class="cta-text">Validation looks good? <strong>Post the ready orders</strong> to SAP B1.</div>
				<button type="button" class="btn btn-primary btn-sm" data-goto-step="3">Next: Post →</button>
			</div>
		</div>
	</section>

	<!-- ═══ Testing · GR Creation (System Manager only) ═════════════════════ -->
	<section id="uc-test-gr-section" style="display:none;margin-bottom:16px;">
		<div class="uc-step-panel" style="border-left:4px solid #f59e0b;">
			<div class="uc-step-header" style="background:#fff7ed;">
				<h2 class="uc-step-heading" style="color:#92400e;">⚠ Testing Only — Create Goods Receipt in SAP B1</h2>
				<p class="uc-step-intro">
					Use when batch validation fails and you need to manually add inventory to SAP.
					This creates a <code>InventoryGenEntries</code> document via SAP B1 Service Layer.
					<strong>Do not use in production without confirmation.</strong>
				</p>
			</div>
			<div class="uc-step-body">
				<div class="uc-sub">
					<div class="uc-sub-title">Add Stock to SAP (Test GR)</div>
					<div class="uc-sub-row" style="flex-wrap:wrap;gap:10px;">
						<div class="uc-field">
							<label>Item Code</label>
							<input id="test-gr-item" type="text" class="form-control form-control-sm" placeholder="e.g. ITEM001" style="width:180px;">
						</div>
						<div class="uc-field">
							<label>Batch Number</label>
							<input id="test-gr-batch" type="text" class="form-control form-control-sm" placeholder="e.g. BATCH001" style="width:180px;">
						</div>
						<div class="uc-field">
							<label>Quantity</label>
							<input id="test-gr-qty" type="number" min="0.001" step="0.001" class="form-control form-control-sm" placeholder="e.g. 10" style="width:100px;">
						</div>
						<div class="uc-field">
							<label>Warehouse</label>
							<input id="test-gr-wh" type="text" class="form-control form-control-sm" placeholder="e.g. EC-FG" style="width:140px;">
						</div>
						<div class="uc-field">
							<label>Doc Date (optional)</label>
							<input id="test-gr-date" type="date" class="form-control form-control-sm" style="width:150px;">
						</div>
						<button id="btn-test-gr-create" class="btn btn-warning btn-sm" style="align-self:flex-end;">Create GR in SAP</button>
					</div>
					<div id="test-gr-result" style="margin-top:10px;font-size:12px;display:none;padding:8px 12px;border-radius:6px;"></div>
				</div>
			</div>
		</div>
	</section>

	<!-- ═══ Step 3 · Post ════════════════════════════════════════════════════ -->
	<section class="uc-step-panel" data-step-panel="3" hidden>
		<div class="uc-step-header">
			<h2 class="uc-step-heading">Step 3 · Post to SAP B1</h2>
			<p class="uc-step-intro">
				Post staged <em>ready</em> orders as AR Invoices, and staged returns as Credit Notes.
				Each click opens a date-range picker that filters by the UC sale-order <code>order_date</code>.
				Invoices must post before credit notes — CNs link back to their parent SAP invoice.
				<br><strong>Strategy:</strong> Post all invoices first, then credit notes, then reconcile (Step 4).
				This is more efficient than post-one/reconcile-one because it minimises SAP API round-trips.
				Per-order SAP DocEntry and any batch hold details are shown live in the terminal below.
			</p>
		</div>
		<div class="uc-step-body">

			<div class="uc-sub">
				<div class="uc-sub-title">Posting Actions</div>
				<div class="uc-sub-row">
					<button id="btn-post-invoices" class="btn btn-primary btn-sm" style="min-width:150px;">Post Invoices</button>
					<button id="btn-post-cn" class="btn btn-default btn-sm" style="min-width:160px;">Post Credit Notes</button>
					<button id="btn-post-all" class="btn btn-default btn-sm" style="min-width:140px;">Post All</button>
					<span class="uc-chip accent" style="align-self:center;margin-left:auto;">
						Per-pass limit configurable · auto-runs every 30 min
					</span>
				</div>
			</div>

			<div id="post-log" class="uc-log" style="display:none;"></div>

			<div class="uc-sub" style="margin-top:var(--gap);">
				<div class="uc-sub-title">AR invoice price audit &amp; SAP cancel</div>
				<p class="uc-helptext" style="margin-top:0;">
					Compares each <strong>posted</strong> UC order in the date window to live SAP AR data using the
					<strong>current</strong> discount-aware unit-price rules (catches the pre-16-Apr-2026 mapper gap).
					Cancel uses Service Layer <code>POST Invoices(DocEntry)/Cancel</code> — blocked if a posted credit note references the same parent SAP DocEntry.
				</p>
				<div class="uc-sub-row" style="flex-wrap:wrap;align-items:flex-end;gap:10px;">
					<label style="margin:0;font-size:12px;">From
						<input type="date" id="audit-price-from" class="form-control input-sm" style="width:150px;margin-top:4px;">
					</label>
					<label style="margin:0;font-size:12px;">To
						<input type="date" id="audit-price-to" class="form-control input-sm" style="width:150px;margin-top:4px;">
					</label>
					<label style="margin:0;font-size:12px;">Max orders
						<select id="audit-price-limit" class="form-control input-sm" style="width:90px;margin-top:4px;">
							<option value="100">100</option>
							<option value="200" selected>200</option>
							<option value="300">300</option>
							<option value="500">500</option>
						</select>
					</label>
					<label style="margin:0;font-size:12px;display:flex;align-items:center;gap:6px;">
						<input type="checkbox" id="audit-price-only-mismatch" checked>
						<span>Only mismatches in response</span>
					</label>
					<button type="button" id="btn-audit-price-mismatch" class="btn btn-default btn-sm">Run price audit</button>
				</div>
				<div id="audit-price-summary" style="font-size:12px;color:var(--text-muted);margin:8px 0 4px;"></div>
				<div id="audit-price-table-wrap" style="display:none;overflow:auto;max-height:320px;border:1px solid var(--border);border-radius:var(--radius-sm);">
					<table class="table table-bordered" style="margin:0;font-size:11px;min-width:720px;">
						<thead><tr>
							<th>UC order</th><th>Channel</th><th>SAP Doc#</th>
							<th style="text-align:right;">SAP tax</th><th style="text-align:right;">Expected tax</th><th>Δ tax</th><th>Line issues</th>
						</tr></thead>
						<tbody id="audit-price-tbody"></tbody>
					</table>
				</div>
				<div class="uc-section-sep" style="margin-top:14px;">Cancel SAP AR invoice</div>
				<div class="uc-sub-row" style="flex-wrap:wrap;gap:10px;align-items:flex-end;">
					<label style="margin:0;font-size:12px;">UC order name OR SAP DocEntry
						<input type="text" id="sap-cancel-ident" class="form-control input-sm" placeholder="b7b46115-… or 45489" style="width:280px;margin-top:4px;">
					</label>
					<label style="margin:0;font-size:12px;display:flex;align-items:center;gap:6px;">
						<input type="checkbox" id="sap-cancel-reset" checked>
						<span>Reset UC order to ready after cancel</span>
					</label>
					<button type="button" id="btn-sap-cancel-preview" class="btn btn-default btn-sm">Preview</button>
					<button type="button" id="btn-sap-cancel-run" class="btn btn-danger btn-sm">Cancel in SAP</button>
				</div>
				<pre id="sap-cancel-preview-out" style="display:none;margin-top:8px;font-size:11px;max-height:200px;overflow:auto;background:#f8f9fa;padding:10px;border-radius:6px;"></pre>
			</div>

			<p class="uc-helptext">
				<strong>Order of operations:</strong> Invoices → Credit Notes → GRN / Inventory.
				If SAP rejects with <em>batch/serial selection incomplete</em>, return to Step 2 and pre-validate.
			</p>

			<div class="uc-next-cta">
				<div class="cta-text">Posting done? <strong>Reconcile UC vs SAP</strong> to catch any drift.</div>
				<button type="button" class="btn btn-primary btn-sm" data-goto-step="4">Next: Reconcile →</button>
			</div>
		</div>
	</section>

	<!-- ═══ Step 4 · Reconcile ═══════════════════════════════════════════════ -->
	<section class="uc-step-panel" data-step-panel="4" hidden>
		<div class="uc-step-header">
			<h2 class="uc-step-heading">Step 4 · Reconcile</h2>
			<p class="uc-step-intro">
				Verify UC orders vs SAP postings for a date range, check price/tax accuracy,
				and run the GST reconciliation.
			</p>
		</div>
		<div class="uc-step-body">

			<!-- Simple date-range reconciliation -->
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div class="uc-sub-title">Order Reconciliation — by Date Range</div>
				<div class="uc-sub-row">
					<div class="uc-field">
						<label>From Date</label>
						<input id="recon-range-from" type="date" class="form-control form-control-sm">
					</div>
					<div class="uc-field">
						<label>To Date</label>
						<input id="recon-range-to" type="date" class="form-control form-control-sm">
					</div>
					<button id="btn-recon-run-simple" class="btn btn-primary btn-sm">Check</button>
				</div>
				<div id="recon-simple-result" style="margin-top:12px;display:none;"></div>
			</div>

			<!-- Finance Recon pane -->
			<div class=”uc-inner-pane” data-inner-pane=”finance”>
				<div class="uc-sub">
					<div class="uc-sub-title">Finance Reconciliation — UC vs SAP</div>
					<p class="uc-helptext">
						Compares Unicommerce order totals (source of truth) against SAP A/R invoice values for a date range.
						Shows channel-wise and customer-wise pivots, matching/not-matching orders, and lets you download an Excel report.
					</p>
					<div class="uc-sub-row">
						<div class="uc-field">
							<label>From Date</label>
							<input id="fin-recon-from" type="date" class="form-control form-control-sm">
						</div>
						<div class="uc-field">
							<label>To Date</label>
							<input id="fin-recon-to" type="date" class="form-control form-control-sm">
						</div>
						<button id="btn-fin-recon-run" class="btn btn-primary btn-sm">Run</button>
						<button id="btn-fin-recon-excel" class="btn btn-default btn-sm" style="display:none;">Download Excel</button>
					</div>
					<div id="fin-recon-status" style="margin-top:8px;font-size:12px;color:var(--text-muted);"></div>
				</div>

				<div id="fin-recon-result" style="display:none;">
					<!-- Summary chips -->
					<div id="fin-recon-summary" style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px;"></div>

					<!-- Channel pivot -->
					<div class="uc-section-sep">Channel-wise Summary</div>
					<div style="overflow-x:auto;margin-bottom:16px;">
						<table class="table table-bordered" id="fin-recon-channel-table" style="font-size:12px;min-width:800px;margin:0;"></table>
					</div>

					<!-- Customer pivot -->
					<div class="uc-section-sep">Customer (SAP)-wise Summary</div>
					<div style="overflow-x:auto;margin-bottom:16px;">
						<table class="table table-bordered" id="fin-recon-customer-table" style="font-size:12px;min-width:800px;margin:0;"></table>
					</div>

					<!-- Not-posted orders -->
					<div class="uc-section-sep">Not Yet Posted to SAP</div>
					<div id="fin-recon-not-posted" style="margin-bottom:16px;overflow-x:auto;"></div>

					<!-- Per-order detail (mismatches first) -->
					<div class="uc-section-sep">Per-Order Detail (mismatches highlighted)</div>
					<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:8px;font-size:12px;">
						<label style="margin:0;">Show:
							<select id="fin-recon-filter" class="form-control input-sm" style="display:inline-block;width:auto;margin-left:6px;">
								<option value="all">All Orders</option>
								<option value="mismatch">Mismatches Only</option>
								<option value="posted">Posted &amp; Matched</option>
								<option value="not_posted">Not Posted</option>
							</select>
						</label>
						<input id="fin-recon-search" type="text" class="form-control input-sm" placeholder="Search order ID / channel" style="width:200px;">
						<button id="btn-fin-recon-filter-apply" class="btn btn-default btn-xs">Apply</button>
					</div>
					<div style="overflow-x:auto;">
						<table class="table table-bordered" id="fin-recon-order-table" style="font-size:12px;min-width:1000px;margin:0;"></table>
					</div>
					<div id="fin-recon-order-pagination" style="display:flex;justify-content:flex-end;align-items:center;gap:8px;margin-top:8px;"></div>
				</div>
			</div>

		</div>
	</section>

	<!-- ═══ Drawers ══════════════════════════════════════════════════════════ -->
	<details class="uc-drawer" id="drawer-failures">
		<summary>
			Failures Triage
			<span class="uc-drawer-badge" id="drawer-failures-badge">0</span>
		</summary>
		<div class="uc-drawer-body">
			<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:14px 0;">
				<label style="font-size:12px;font-weight:600;margin:0;">Stage:</label>
				<select id="failures-stage-filter" class="form-control form-control-sm" style="width:160px;font-size:12px;">
					<option value="all">All Stages</option>
					<option value="orders">Orders</option>
					<option value="credit_notes">Credit Notes</option>
					<option value="inventory">Inventory</option>
				</select>
				<button id="btn-load-failures" class="btn btn-default btn-xs">Refresh</button>
				<button id="btn-failures-select-all" class="btn btn-default btn-xs">Select All</button>
				<button id="btn-failures-bulk-queue" class="btn btn-default btn-xs">Queue Selected</button>
				<button id="btn-failures-bulk-now" class="btn btn-default btn-xs">Retry Selected Now</button>
				<span id="failures-selected-count" class="uc-chip">Selected: 0</span>
				<span style="font-size:11px;color:var(--text-muted);margin-left:auto;">Queue = reset for next scheduler run · Retry Now = synchronous</span>
			</div>
			<div style="overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius-sm);">
				<table class="table table-bordered" style="margin:0;font-size:12px;min-width:900px;">
					<thead>
						<tr>
							<th style="width:32px;text-align:center;">✓</th>
							<th>Stage</th><th>External ID</th><th>Status</th><th>Attempts</th>
							<th>Last Error</th><th>Modified</th><th>Actions</th>
						</tr>
					</thead>
					<tbody id="failures-tbody">
						<tr><td colspan="8" style="text-align:center;color:var(--text-muted);padding:24px;">Click Refresh to load failures.</td></tr>
					</tbody>
				</table>
				<div id="failures-pagination" style="display:flex;justify-content:flex-end;align-items:center;gap:8px;padding:10px 12px;"></div>
			</div>
		</div>
	</details>

	<details class="uc-drawer" id="drawer-more">
		<summary>
			More Tools · Monitoring · Analytics · Guardrails · Returns
			<span class="uc-drawer-badge">Optional</span>
		</summary>
		<div class="uc-drawer-body">

			<div class="uc-section-sep">Activity · Last 24 Hours</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div class="ops-grid-2">
					<div>
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);font-weight:600;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border);">Scheduled Job Runs</div>
						<div id="activity-jobs" style="font-size:12px;"></div>
					</div>
					<div>
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);font-weight:600;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid var(--border);">Error Log</div>
						<div id="activity-errors" class="uc-log" style="min-height:120px;max-height:300px;"></div>
					</div>
				</div>
			</div>

			<div class="uc-section-sep">Monitoring · Pipeline Health</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div id="monitor-trend-chips" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:var(--gap);"></div>
				<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--gap-sm);">
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;">
						<div style="font-size:12px;font-weight:700;margin-bottom:8px;">Queue Pressure</div>
						<div id="monitor-queue-pressure"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;">
						<div style="font-size:12px;font-weight:700;margin-bottom:8px;">CN Blockers</div>
						<div id="monitor-cn-blockers"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;">
						<div style="font-size:12px;font-weight:700;margin-bottom:8px;">Data Integrity Risk</div>
						<div id="monitor-integrity-risk"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;">
						<div style="font-size:12px;font-weight:700;margin-bottom:8px;">Ops Health Score</div>
						<div id="monitor-health-score"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;grid-column:1/-1;">
						<div style="font-size:12px;font-weight:700;margin-bottom:8px;">At-risk Channels (Guardrails)</div>
						<div id="monitor-risk-channels"></div>
					</div>
				</div>
			</div>

			<div class="uc-section-sep">Pipeline Detail</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:var(--gap-sm);">
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;">
						<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
							<div style="font-size:13px;font-weight:700;">Orders</div>
							<div id="orders-total" class="uc-chip">-</div>
						</div>
						<div id="orders-bars"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;">
						<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
							<div style="font-size:13px;font-weight:700;">Credit Notes</div>
							<div id="cn-total" class="uc-chip">-</div>
						</div>
						<div id="cn-bars"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;">
						<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
							<div style="font-size:13px;font-weight:700;">Inventory Sync</div>
							<div id="inv-total" class="uc-chip">-</div>
						</div>
						<div id="inv-bars"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;">
						<div style="font-size:13px;font-weight:700;margin-bottom:10px;">Worker Last Runs</div>
						<div id="worker-runs" style="font-size:12px;"></div>
					</div>
				</div>
				<div style="margin-top:var(--gap);font-size:12px;color:var(--text-muted);">
					Active Failures: <span id="stat-failures" style="font-weight:700;color:var(--bad);">-</span>
					&nbsp;·&nbsp; Recon Gaps: <span id="stat-recon" style="font-weight:700;color:var(--warn);">-</span>
				</div>
			</div>

			<div class="uc-section-sep">Order Coverage · Uniware vs SAP</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:var(--gap);">
					<button id="btn-coverage-refresh" class="btn btn-default btn-xs">Refresh</button>
					<span id="coverage-status" style="font-size:12px;color:var(--text-muted);">Loading…</span>
				</div>
				<div style="display:flex;gap:var(--gap-sm);flex-wrap:wrap;margin-bottom:var(--gap);">
					${stat_card('Total Orders',          'cov-total',          'var(--text)')}
					${stat_card('Uniware COMPLETE',      'cov-complete',       'var(--ok)')}
					${stat_card('Uniware CANCELLED',     'cov-cancelled',      '#6c757d')}
					${stat_card('Posted to SAP',         'cov-posted',         'var(--accent)')}
					${stat_card('Not Posted',            'cov-not-posted',     'var(--warn)')}
					${stat_card('Never Attempted',       'cov-never',          '#adb5bd')}
				</div>

				<div class="ops-grid-2" style="gap:var(--gap);margin-bottom:var(--gap);">
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;">
						<div style="font-size:13px;font-weight:700;margin-bottom:10px;">Pipeline Status (all orders)</div>
						<div id="cov-pipeline-bars"></div>
					</div>
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px;">
						<div style="font-size:13px;font-weight:700;margin-bottom:10px;">Uniware Status (all orders)</div>
						<div id="cov-uniware-bars"></div>
					</div>
				</div>

				<div style="font-size:13px;font-weight:700;margin-bottom:8px;">Channel-wise Coverage</div>
				<div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
					Counts across the entire <code>tabUnicommerce Orders</code> table — not date-filtered.
					<strong>Complete</strong> = Uniware <code>status</code> starts with <em>COMPL*</em>.
					<strong>Posted</strong> = SAP AR Invoice DocEntry is set.
				</div>
				<div style="overflow-x:auto;">
					<table class="table table-bordered" style="margin:0;font-size:12px;min-width:900px;">
						<thead>
							<tr>
								<th>Channel</th>
								<th style="text-align:right;">Total</th>
								<th style="text-align:right;">Complete</th>
								<th style="text-align:right;">Posted</th>
								<th style="text-align:right;">Not Posted</th>
								<th style="text-align:right;">Fetched</th>
								<th style="text-align:right;">Ready</th>
								<th style="text-align:right;">Batch Hold</th>
								<th style="text-align:right;">Failed</th>
								<th style="text-align:right;">Dead</th>
								<th style="min-width:120px;">Posted Share</th>
							</tr>
						</thead>
						<tbody id="cov-channel-tbody">
							<tr><td colspan="11" style="text-align:center;color:var(--text-muted);padding:16px;">Loading…</td></tr>
						</tbody>
					</table>
				</div>
			</div>

			<div class="uc-section-sep">Posting Guardrails</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:var(--gap);">
					<select id="guardrail-filter" class="form-control form-control-sm" style="width:170px;font-size:12px;">
						<option value="active">Active Queue</option>
						<option value="ready">Ready Only</option>
						<option value="batch_hold">Batch Hold Only</option>
						<option value="failed">Failed/Dead</option>
						<option value="all">All Statuses</option>
					</select>
					<button id="btn-guardrail-refresh" class="btn btn-default btn-xs">Apply</button>
					<span id="guardrail-status" style="font-size:12px;color:var(--text-muted);">Loading…</span>
				</div>
				<div id="guardrail-summary" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:var(--gap-sm);"></div>
				<div id="guardrail-table-wrap" style="overflow-x:auto;display:none;">
					<table class="table table-bordered" style="margin:0;font-size:12px;min-width:880px;">
						<thead>
							<tr>
								<th>Channel</th>
								<th style="text-align:right;">Orders</th>
								<th style="text-align:right;">Shipping Lines</th>
								<th style="text-align:right;">Shipping Tax Missing</th>
								<th style="text-align:right;">Missing Vendor Batch</th>
								<th style="text-align:right;">Missing Uniware Batch</th>
								<th style="text-align:right;">Batch Hold Orders</th>
							</tr>
						</thead>
						<tbody id="guardrail-tbody"></tbody>
					</table>
				</div>
			</div>

			<div class="uc-section-sep">Returns Cross-Check</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:var(--gap);">
					<button id="btn-load-returns" class="btn btn-default btn-sm">Refresh Returns</button>
					<button id="btn-retry-failed-cn-now" class="btn btn-default btn-sm">Retry Failed CN Now</button>
					<button id="btn-retry-pending-cn-ready-parent" class="btn btn-default btn-sm">Retry Pending CN (Parent Posted)</button>
					<button id="btn-debug-uc-returns" class="btn btn-default btn-sm" title="Probe UC API to find working request format">Debug UC Returns API</button>
				</div>
				<div id="returns-summary-cards" style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:var(--gap-sm);"></div>
				<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:var(--gap-sm);">
					<button class="btn btn-default btn-xs uc-cn-filter active" data-cn-filter="all">All</button>
					<button class="btn btn-default btn-xs uc-cn-filter" data-cn-filter="pending">Pending</button>
					<button class="btn btn-default btn-xs uc-cn-filter" data-cn-filter="failed">Failed</button>
					<button class="btn btn-default btn-xs uc-cn-filter" data-cn-filter="posted">Posted</button>
					<button class="btn btn-default btn-xs uc-cn-filter" data-cn-filter="blocked">Blocked (Parent not posted)</button>
				</div>
				<div id="returns-table-wrap" style="overflow-x:auto;display:none;">
					<table class="table table-bordered" style="margin:0;font-size:12px;min-width:900px;">
						<thead>
							<tr>
								<th>Return ID</th>
								<th>Parent Order</th>
								<th>Return Date</th>
								<th>Type</th>
								<th>CN Status</th>
								<th>Parent Status</th>
								<th>SAP Doc Entry</th>
								<th>Last Error</th>
								<th>Actions</th>
							</tr>
						</thead>
						<tbody id="returns-tbody"></tbody>
					</table>
					<div id="returns-pagination" style="display:flex;justify-content:flex-end;align-items:center;gap:8px;padding:10px 2px;"></div>
				</div>
			</div>

			<div class="uc-section-sep">Analytics · Channel &amp; Tax Breakdown</div>
			<div class="uc-sub" style="margin-bottom:var(--gap);">
				<div class="uc-sub-row" style="margin-bottom:var(--gap);">
					<div class="uc-field">
						<label>From</label>
						<input id="analytics-start" type="date" class="form-control form-control-sm" style="width:150px;" value="${frappe.datetime.month_start()}">
					</div>
					<div class="uc-field">
						<label>To</label>
						<input id="analytics-end" type="date" class="form-control form-control-sm" style="width:150px;" value="${frappe.datetime.month_end()}">
					</div>
					<button id="btn-analytics-load" class="btn btn-primary btn-xs">Load</button>
					<button id="btn-analytics-this-month" class="btn btn-default btn-xs">This Month</button>
					<button id="btn-analytics-prev-month" class="btn btn-default btn-xs">Prev Month</button>
				</div>
				<div style="display:flex;gap:var(--gap-sm);flex-wrap:wrap;margin-bottom:var(--gap);">
					${stat_card('Total Invoices Posted', 'a-total-inv', 'var(--ok)')}
					${stat_card('Total Credit Notes', 'a-total-cn', '#6f42c1')}
					${stat_card('Total Tax (SAP)', 'a-total-tax', 'var(--text)')}
					${stat_card('IGST Orders', 'a-igst-cnt', 'var(--accent)')}
					${stat_card('IGST Tax', 'a-igst-tax', 'var(--accent)')}
					${stat_card('CGST+SGST Orders', 'a-cgst-cnt', '#6f42c1')}
					${stat_card('CGST+SGST Tax', 'a-cgst-tax', '#6f42c1')}
				</div>
				<div style="margin-bottom:var(--gap);">
					<div style="font-size:13px;font-weight:700;margin-bottom:10px;">Tax Type Breakdown (Orders Count)</div>
					<div id="tax-type-bars"></div>
				</div>
				<div style="font-size:13px;font-weight:700;margin-bottom:10px;">Channel-wise Breakdown</div>
				<div id="analytics-status" style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">Pick a date range and click Load.</div>
				<div style="overflow-x:auto;">
					<table class="table table-bordered" style="margin:0;font-size:12px;min-width:600px;">
						<thead>
							<tr>
								<th>Channel</th>
								<th style="text-align:right;">Orders Posted</th>
								<th style="text-align:right;">Total Tax (SAP)</th>
								<th style="text-align:right;">Recon Gaps</th>
								<th>Share</th>
							</tr>
						</thead>
						<tbody id="channel-tbody">
							<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:20px;">Click Load.</td></tr>
						</tbody>
					</table>
				</div>
			</div>

			<div id="admin-tools-panel" class="uc-sub" style="display:${IS_ADMIN ? 'block' : 'none'};margin-bottom:0;">
				<div class="uc-sub-title">Admin · Diagnostics</div>
				<div style="display:flex;gap:8px;flex-wrap:wrap;">
					<button id="btn-analyze-return-ids" class="btn btn-default btn-xs">Analyze Return ID Extraction</button>
				</div>
				<p class="uc-helptext" style="margin:10px 0 0;">Visible only to System Manager / Administrator. Use when debugging UC return-ID extraction.</p>
			</div>
		</div>
	</details>

	<!-- ═══ Step 5 · Inward Inventory (SAP → UC PO + GRN) ═══════════════════ -->
	<section class="uc-step-panel" data-step-panel="5" hidden>
		<div class="uc-step-header">
			<h2 class="uc-step-heading">Step 5 · Inward Inventory — SAP → Unicommerce</h2>
			<p class="uc-step-intro">
				When goods arrive at the <strong>EC-FG</strong> (Finished Goods) warehouse in SAP via
				an Inventory Transfer, Unicommerce needs to know about it — otherwise UC shows
				wrong stock and orders may fail to allocate. This tab handles that sync.
			</p>
		</div>
		<div class="uc-step-body">

			<!-- ── How it works ──────────────────────────────────────────────── -->
			<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:var(--gap-sm);margin-bottom:var(--gap-lg);">
				<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 16px;background:var(--surface-muted);">
					<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--text-muted);margin-bottom:6px;">Step A — SAP Records Stock</div>
					<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px);">SAP Inventory Transfer</div>
					<div style="font-size:12px;color:var(--text-muted);line-height:1.55;">
						A warehouse manager creates a <strong>Stock Transfer</strong> in SAP B1 moving goods
						<em>into</em> EC-FG. SAP updates its batch inventory immediately.
					</div>
				</div>
				<div style="display:flex;align-items:center;justify-content:center;font-size:22px;color:var(--text-muted);">→</div>
				<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 16px;background:var(--surface-muted);">
					<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--accent);margin-bottom:6px;">Step B — We Create a UC PO</div>
					<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px;">Purchase Order in Unicommerce</div>
					<div style="font-size:12px;color:var(--text-muted);line-height:1.55;">
						This tab creates an <strong>APPROVED Purchase Order</strong> in Unicommerce listing
						all SKUs from the SAP transfer. UC now expects a delivery.
					</div>
				</div>
				<div style="display:flex;align-items:center;justify-content:center;font-size:22px;color:var(--text-muted);">→</div>
				<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 16px;background:var(--surface-muted);">
					<div style="font-size:10px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--ok);margin-bottom:6px;">Step C — We Create UC GRN(s)</div>
					<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px;">Goods Receipt Note (Inflow)</div>
					<div style="font-size:12px;color:var(--text-muted);line-height:1.55;">
						One or more <strong>GRNs</strong> are created against the PO — one per batch line.
						Each GRN carries the vendor batch number and expiry date from SAP.
						UC inventory is updated.
					</div>
				</div>
			</div>

			<!-- ── Live Unicommerce warning ───────────────────────────────────── -->
			<div style="display:flex;align-items:flex-start;gap:10px;padding:12px 16px;border:1px solid #ffc107;border-radius:var(--radius-sm);background:#fffbeb;margin-bottom:var(--gap-lg);">
				<span style="font-size:16px;flex-shrink:0;">⚠️</span>
				<div style="font-size:12px;color:#92400e;line-height:1.6;">
					<strong>Live Unicommerce — no test environment.</strong>
					Every "Process" and "Create GRN" action writes directly to the production Unicommerce account.
					A confirmation dialog will appear before any write. Do <em>not</em> click Process unless
					the SAP Inventory Transfer is fully posted and approved.
					The system checks for an existing UC PO before creating a new one, so re-running is safe.
				</div>
			</div>

			<!-- ── Section A: SAP Inward Transfers ───────────────────────────── -->
			<div class="uc-section-sep">Section A · SAP Inward Transfers → Unicommerce PO + GRN</div>
			<div class="uc-sub">
				<div class="uc-sub-title">How to use this section</div>
				<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:var(--gap);">
					<div style="font-size:12px;color:var(--text-muted);line-height:1.6;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-muted);">
						<strong style="color:var(--text);display:block;margin-bottom:3px;">1 · Refresh</strong>
						Click <em>Refresh List</em> to see all SAP inventory transfers going <strong>into EC-FG</strong>
						in the selected date range, along with their current UC sync status.
					</div>
					<div style="font-size:12px;color:var(--text-muted);line-height:1.6;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-muted);">
						<strong style="color:var(--text);display:block;margin-bottom:3px;">2 · Check Status</strong>
						<span class="uc-chip" style="font-size:10px;padding:1px 7px;background:#fee2e2;color:#b91c1c;">No PO</span> means not yet synced to UC.<br>
						<span class="uc-chip" style="font-size:10px;padding:1px 7px;background:#dbeafe;color:#1d4ed8;">PO Created</span> PO exists, GRN pending.<br>
						<span class="uc-chip" style="font-size:10px;padding:1px 7px;background:#dcfce7;color:#15803d;">GRN Done</span> fully synced to UC.
					</div>
					<div style="font-size:12px;color:var(--text-muted);line-height:1.6;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-muted);">
						<strong style="color:var(--text);display:block;margin-bottom:3px;">3 · Process</strong>
						Use <em>Process</em> on a single row to sync one transfer.
						Use <em>Process All Pending</em> to queue a background job for all
						<span style="color:#b91c1c;font-weight:700;">No PO</span> transfers at once.
					</div>
				</div>

				<!-- Controls row -->
				<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:var(--gap);">
					<div class="uc-field">
						<label>Date Range (days back)</label>
						<input id="inward-days" type="number" value="30" min="1" max="365"
							class="form-control form-control-sm" style="width:90px;" title="Look back this many days for inward transfers">
					</div>
					<button id="btn-inward-refresh" class="btn btn-default btn-sm">
						↻ Refresh List
					</button>
					<button id="btn-inward-process-all" class="btn btn-primary btn-sm" disabled title="Queues a background job to process all transfers with No PO status">
						⚡ Process All Pending
					</button>
					<span id="inward-status" style="font-size:12px;color:var(--text-muted);align-self:center;">
						Click <em>Refresh List</em> to load transfers.
					</span>
				</div>

				<!-- Summary stat cards -->
				<div id="inward-summary-cards" style="display:none;margin-bottom:var(--gap);">
					<div style="display:flex;gap:10px;flex-wrap:wrap;">
						<div style="border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px 16px;background:var(--surface);min-width:110px;text-align:center;">
							<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted);font-weight:600;">Total</div>
							<div id="inward-count-total" style="font-size:22px;font-weight:700;color:var(--text);">—</div>
						</div>
						<div style="border:1px solid #fee2e2;border-radius:var(--radius-sm);padding:10px 16px;background:#fff5f5;min-width:110px;text-align:center;">
							<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#b91c1c;font-weight:600;">No PO</div>
							<div id="inward-count-pending" style="font-size:22px;font-weight:700;color:#b91c1c;">—</div>
						</div>
						<div style="border:1px solid #dbeafe;border-radius:var(--radius-sm);padding:10px 16px;background:#eff6ff;min-width:110px;text-align:center;">
							<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#1d4ed8;font-weight:600;">PO Created</div>
							<div id="inward-count-po" style="font-size:22px;font-weight:700;color:#1d4ed8;">—</div>
						</div>
						<div style="border:1px solid #fde68a;border-radius:var(--radius-sm);padding:10px 16px;background:#fffbeb;min-width:110px;text-align:center;">
							<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#92400e;font-weight:600;">GRN Partial</div>
							<div id="inward-count-partial" style="font-size:22px;font-weight:700;color:#92400e;">—</div>
						</div>
						<div style="border:1px solid #bbf7d0;border-radius:var(--radius-sm);padding:10px 16px;background:#f0fdf4;min-width:110px;text-align:center;">
							<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#15803d;font-weight:600;">GRN Done</div>
							<div id="inward-count-done" style="font-size:22px;font-weight:700;color:#15803d;">—</div>
						</div>
					</div>
				</div>

				<!-- Transfers table -->
				<div id="inward-table-wrap" style="display:none;">
					<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">
						Showing SAP Inventory Transfers (To Warehouse = <strong>EC-FG</strong>) —
						sorted newest first. Click <strong>Process</strong> on any row to push it to Unicommerce.
					</div>
					<div style="overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius-sm);">
						<table class="table table-bordered" style="margin:0;font-size:12px;min-width:860px;">
							<thead style="position:sticky;top:0;z-index:1;background:var(--surface-muted);">
								<tr>
									<th title="SAP Inventory Transfer document number">Transfer No.</th>
									<th title="Date the transfer was recorded in SAP">Date</th>
									<th title="Source warehouse in SAP">From Warehouse</th>
									<th title="Unicommerce Purchase Order code (set after processing)">UC PO Code</th>
									<th title="GRN numbers created in Unicommerce (comma-separated if multiple)">UC GRN(s)</th>
									<th title="Current sync status between SAP and Unicommerce">Sync Status</th>
									<th style="text-align:center;" title="Trigger PO + GRN creation in Unicommerce">Action</th>
								</tr>
							</thead>
							<tbody id="inward-tbody">
								<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:24px;">
									Click <strong>Refresh List</strong> to load transfers.
								</td></tr>
							</tbody>
						</table>
					</div>
					<div id="inward-last-refreshed" style="font-size:11px;color:var(--text-muted);margin-top:6px;text-align:right;"></div>
				</div>

				<!-- Inline result for single-row processing -->
				<div id="inward-process-result" style="display:none;margin-top:12px;"></div>
			</div>

			<!-- ── Section B: Manual UC PO → GRN ─────────────────────────────── -->
			<div class="uc-section-sep">Section B · Manual UC PO → GRN</div>
			<div class="uc-sub">
				<div class="uc-sub-title">When to use this section</div>
				<div style="font-size:12px;color:var(--text-muted);line-height:1.6;padding:10px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface-muted);margin-bottom:var(--gap);">
					Sometimes a warehouse operator creates a <strong>Purchase Order directly inside Unicommerce</strong>
					(not triggered by a SAP transfer). In that case there is no SAP Inventory Transfer to process via
					Section A. Use this section to look up that UC PO and create the GRN so that UC inventory
					is received and stock is reflected.<br><br>
					<strong>Steps:</strong>
					Enter the UC PO code (e.g. <code>PO0026</code>) →
					Click <em>Look Up PO</em> to verify it exists and see its items →
					Click <em>Create GRN</em> to receive the stock in Unicommerce.
				</div>

				<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:var(--gap);">
					<div class="uc-field">
						<label>Unicommerce PO Code</label>
						<input id="manual-po-code" type="text" class="form-control form-control-sm"
							placeholder="e.g. PO0026" style="width:180px;"
							title="Enter the PO code exactly as shown in Unicommerce">
					</div>
					<button id="btn-manual-po-lookup" class="btn btn-default btn-sm"
						title="Read-only — fetches PO details from Unicommerce without making any changes">
						🔍 Look Up PO
					</button>
					<button id="btn-manual-po-grn" class="btn btn-primary btn-sm" disabled
						title="Creates GRN in live Unicommerce — you will be asked to confirm first">
						✚ Create GRN
					</button>
				</div>

				<!-- Lookup result card -->
				<div id="manual-po-result" style="display:none;margin-top:4px;">
					<div style="border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden;">
						<!-- PO header -->
						<div id="manual-po-info" style="padding:12px 16px;background:var(--surface-muted);font-size:12px;border-bottom:1px solid var(--border);"></div>
						<!-- Items table -->
						<div style="padding:12px 16px;">
							<div style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;font-weight:700;color:var(--text-muted);margin-bottom:8px;">
								PO Line Items
								<span style="font-weight:400;text-transform:none;font-size:11px;color:var(--text-muted);">
									— GRN will receive all of these into UC inventory
								</span>
							</div>
							<div style="overflow-x:auto;">
								<table class="table table-bordered" style="margin:0;font-size:12px;max-width:480px;">
									<thead>
										<tr>
											<th>SKU Code</th>
											<th style="text-align:right;">Ordered Qty</th>
										</tr>
									</thead>
									<tbody id="manual-po-tbody"></tbody>
								</table>
							</div>
							<p class="uc-helptext" style="margin-top:10px;">
								<strong>Note:</strong> Since this PO was created directly in Unicommerce (no SAP source),
								the GRN will be created with batch number set to <code>NA</code>.
								If you need batch-level tracking, process the corresponding SAP Inventory Transfer via Section A instead.
							</p>
						</div>
					</div>
				</div>

				<!-- GRN creation result -->
				<div id="manual-grn-result" style="display:none;margin-top:12px;"></div>
			</div>

		</div>
	</section>

</div>

	`);

	// ═══ Wizard navigation ══════════════════════════════════════════════════
	// Tracks which wizard step the operator is viewing. Step panels are shown
	// one at a time; the stepper tabs + any element with [data-goto-step] drive
	// the switch. A step is marked "done" the first time the operator advances
	// past it, giving a simple progress-trail without needing server state.

	const WIZARD = { current: 1, done: new Set() };

	function activate_step(n) {
		const step = Math.max(1, Math.min(5, Number(n) || 1));
		if (step === WIZARD.current) return;
		if (step > WIZARD.current) WIZARD.done.add(WIZARD.current);
		WIZARD.current = step;
		$(wrapper).find('.uc-step-tab').each(function () {
			const s = Number($(this).attr('data-step'));
			$(this).toggleClass('active', s === step).attr('aria-selected', s === step);
			$(this).toggleClass('done', WIZARD.done.has(s) && s !== step);
		});
		$(wrapper).find('.uc-step-panel').each(function () {
			const s = Number($(this).attr('data-step-panel'));
			$(this).attr('hidden', s === step ? null : 'hidden');
		});
		// Scroll to panel top so the operator sees the new step cleanly.
		const $panel = $(wrapper).find(`[data-step-panel="${step}"]`);
		if ($panel.length) {
			$('html, body').animate({ scrollTop: $panel.offset().top - 80 }, 200);
		}
		// Lazy-load step-scoped data when it first becomes visible.
		// (GST recon removed — Finance Recon is user-triggered)
	}

	$(wrapper).on('click', '.uc-step-tab', function () {
		activate_step($(this).attr('data-step'));
	});
	$(wrapper).on('click', '[data-goto-step]', function () {
		activate_step($(this).attr('data-goto-step'));
	});

	// Inner tabs (no-op — Finance Recon pane is always visible in Step 4).
	$(wrapper).on('click', '.uc-inner-tab', function () {
		const key = $(this).attr('data-inner-tab');
		const $root = $(this).closest('.uc-step-body');
		$root.find('.uc-inner-tab').removeClass('active');
		$(this).addClass('active');
		$root.find('.uc-inner-pane').each(function () {
			const match = $(this).attr('data-inner-pane') === key;
			$(this).attr('hidden', match ? null : 'hidden');
		});
	});

	// ═══ Testing section (System Manager only) ══════════════════════════════
	if (IS_ADMIN) {
		$(wrapper).find('#uc-test-gr-section').show();
	}

	$(wrapper).find('#btn-test-gr-create').on('click', function () {
		const $btn = $(this);
		const item   = $(wrapper).find('#test-gr-item').val().trim();
		const batch  = $(wrapper).find('#test-gr-batch').val().trim();
		const qty    = parseFloat($(wrapper).find('#test-gr-qty').val() || '0');
		const wh     = $(wrapper).find('#test-gr-wh').val().trim();
		const ddate  = $(wrapper).find('#test-gr-date').val().trim();
		const $res   = $(wrapper).find('#test-gr-result');

		if (!item || !batch || !wh || !(qty > 0)) {
			frappe.msgprint('Fill in Item Code, Batch Number, Warehouse, and Quantity > 0.');
			return;
		}
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Creating…');
		$res.hide();

		frappe.call({
			method: API + '.ops_create_test_gr',
			args: { item_code: item, batch_number: batch, quantity: qty, warehouse_code: wh, doc_date: ddate || null },
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				const d = r && r.message;
				if (d && d.ok) {
					$res.show().css({ background: '#dcfce7', color: '#166534', border: '1px solid #86efac' })
						.text(`✓ ${d.message}`);
					frappe.show_alert({ message: d.message, indicator: 'green' }, 6);
				} else {
					$res.show().css({ background: '#fee2e2', color: '#991b1b', border: '1px solid #fca5a5' })
						.text(`Error: ${(d && d.error) || 'Unknown error'}`);
				}
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				$res.show().css({ background: '#fee2e2', color: '#991b1b', border: '1px solid #fca5a5' })
					.text('Request failed — check Error Log.');
			},
		});
	});

	// ═══ Hero metric updater ════════════════════════════════════════════════
	// Mirrors the current `counts` payload from ops_overview onto the six
	// at-a-glance hero tiles. Also refreshes the Failures drawer badge so the
	// operator sees when triage work exists without having to expand it.

	function render_hero_tiles(counts) {
		const orders = (counts && counts.orders) || {};
		const cn     = (counts && counts.credit_notes) || {};
		const fetched     = Number(orders.fetched || 0);
		const ready       = Number(orders.ready || 0);
		const batch_hold  = Number(orders.batch_hold || 0);
		const failed_all  = Number(orders.failed || 0) + Number(orders.dead || 0)
			+ Number(cn.failed || 0) + Number(cn.dead || 0);
		const cn_pending  = Number(cn.pending || 0);

		$('#hero-fetched').text(fmt(fetched));
		$('#hero-ready').text(fmt(ready));
		$('#hero-batch-hold').text(fmt(batch_hold));
		$('#hero-failed').text(fmt(failed_all));
		$('#hero-cn-ready').text(fmt(cn_pending));

		const $fbadge = $('#drawer-failures-badge');
		$fbadge.text(fmt(failed_all));
		$fbadge.toggleClass('has-work', failed_all > 0);
	}

	// ─── Dashboard ───────────────────────────────────────────────────────────

	function load_dashboard() {
		if (!acquire_request_lock('dashboard')) return;
		$('#dashboard-status').text('Loading dashboard…');
		frappe.call({
			method: API + '.ops_overview',
			freeze: false,
			callback: function (r) {
				release_request_lock('dashboard');
				if (!r.message) return;
				const d = r.message;
				render_health(d.health);
				render_counts(d.counts, d.recon_summary);
				render_hero_tiles(d.counts);
				render_workers(d.last_runs);
				load_guardrails();
				$('#dashboard-status').text('Refreshed at ' + new Date().toLocaleTimeString());
				load_failures();
			},
			error: function () {
				release_request_lock('dashboard');
				$('#dashboard-status').html('<span style="color:#dc3545;">Failed to load</span>');
			},
		});
	}

	// ─── Health ──────────────────────────────────────────────────────────────

	function render_health(health) {
		set_health_card('#health-sap', 'SAP', health && health.sap_login);
		set_health_card('#health-uc',  'UC',  health && health.uc_login);
	}

	// Renders a compact single-line health row inside the Health hero tile:
	// ``• SAP · Connected``. The dot colour and tooltip carry the detail so
	// the tile stays dense but still has the full status message on hover.
	function set_health_card(sel, label, result) {
		const ok = Boolean(result && result.ok);
		const msg = (result && result.message) || '';
		const dotClass = ok ? 'ok' : 'bad';
		const statusText = ok ? 'Connected' : 'Disconnected';
		const titleAttr = msg ? ` title="${esc(msg)}"` : '';
		$(wrapper).find(sel).html(
			`<span class="uc-dot ${dotClass}"${titleAttr}></span>` +
			`<span style="font-weight:600;">${esc(label)}</span> ` +
			`<span style="color:var(--text-muted);font-weight:500;">· ${statusText}</span>`
		);
	}

	function render_counts(counts, recon) {
		const o = counts.orders || {}, cn = counts.credit_notes || {}, inv = counts.inventory || {};
		const fails = (o.failed||0)+(o.dead||0)+(cn.failed||0)+(cn.dead||0)+(inv.Failed||0)+(inv.Partial||0);
		$('#stat-failures').text(fmt(fails)).css('color', fails > 0 ? '#dc3545' : '#28a745');
		const gaps = recon && recon.gap_count !== undefined ? recon.gap_count : 0;
		$('#stat-recon').text(fmt(gaps)).css('color', gaps > 0 ? '#fd7e14' : '#28a745');
		$('#orders-total').text(fmt(o._total||0));
		$('#cn-total').text(fmt(cn._total||0));
		$('#inv-total').text(fmt(inv._total||0));
		$('#orders-bars').html(pipeline_bars(o, ORDER_COLOR));
		$('#cn-bars').html(pipeline_bars(cn, CN_COLOR));
		$('#inv-bars').html(pipeline_bars(inv, INV_COLOR));
		MONITOR_STATE.counts = counts || null;
		MONITOR_STATE.recon = recon || null;
		render_monitoring_panels();
	}

	function render_monitoring_panels() {
		const counts = MONITOR_STATE.counts || {};
		const returns = MONITOR_STATE.returns || {};
		const failures = MONITOR_STATE.failures || {};
		const recon = MONITOR_STATE.recon || {};
		const guardrails = MONITOR_STATE.guardrails || {};

		const o = counts.orders || {};
		const cn = counts.credit_notes || {};
		const total_orders = Number(o._total || 0);
		const order_backlog = Number(o.ready || 0) + Number(o.batch_hold || 0) + Number(o.failed || 0) + Number(o.dead || 0);
		const cn_total = Number(cn._total || 0);
		const cn_pending = Number(cn.pending || 0);
		const cn_failed = Number(cn.failed || 0) + Number(cn.dead || 0);
		const pending_parent_not_posted = Number(returns.pending_parent_not_posted || 0);
		const gap_count = Number(recon.gap_count || 0);
		const failure_total = Number(failures.total || 0);
		const hard_failures = Number(failures.hard || 0);
		const channels = Array.isArray(guardrails.channels) ? guardrails.channels : [];

		$('#monitor-queue-pressure').html(
			progress_row('Order Backlog', order_backlog, total_orders || 1, UI.blue) +
			progress_row('CN Pending', cn_pending, cn_total || 1, UI.amber) +
			progress_row('Hard Failures', hard_failures, Math.max(failure_total, 1), UI.red)
		);

		$('#monitor-cn-blockers').html(
			progress_row('Parent Not Posted', pending_parent_not_posted, Math.max(cn_pending, 1), UI.amber) +
			progress_row('CN Failed/Dead', cn_failed, Math.max(cn_total, 1), UI.red) +
			progress_row('CN Posted', Number(cn.posted || 0), Math.max(cn_total, 1), UI.green)
		);

		$('#monitor-integrity-risk').html(
			progress_row('Recon Gaps', gap_count, Math.max(total_orders, 1), UI.purple) +
			progress_row('Failed Orders', Number(o.failed || 0) + Number(o.dead || 0), Math.max(total_orders, 1), UI.red) +
			progress_row('Batch Hold Orders', Number(o.batch_hold || 0), Math.max(total_orders, 1), UI.purple)
		);

		const score_penalty = Math.min(100,
			Math.round((order_backlog / Math.max(total_orders || 1, 1)) * 45) +
			Math.round((gap_count / Math.max(total_orders || 1, 1)) * 30) +
			Math.round((hard_failures / Math.max(total_orders || 1, 1)) * 25)
		);
		const score = Math.max(0, 100 - score_penalty);
		const score_color = score >= 85 ? UI.green : score >= 65 ? UI.amber : UI.red;
		$('#monitor-health-score').html(`
			<div style="display:flex;align-items:flex-end;gap:8px;margin-bottom:6px;">
				<div style="font-size:30px;line-height:1;font-weight:800;color:${score_color};">${score}</div>
				<div style="font-size:12px;color:#6c757d;margin-bottom:3px;">/100</div>
			</div>
			<div style="height:10px;background:#eef2f6;border-radius:6px;overflow:hidden;margin-bottom:8px;">
				<div style="height:100%;width:${score}%;background:${score_color};border-radius:6px;"></div>
			</div>
			<div style="font-size:11px;color:#6c757d;">Penalty mix: backlog, recon gaps, and hard failures.</div>
		`);

		const backlog_pct = total_orders > 0 ? Math.round((order_backlog / total_orders) * 100) : 0;
		const cn_block_pct = cn_pending > 0 ? Math.round((pending_parent_not_posted / cn_pending) * 100) : 0;
		const failure_pct = total_orders > 0 ? Math.round((hard_failures / total_orders) * 100) : 0;
		$('#monitor-trend-chips').html([
			trend_chip('Backlog', `${backlog_pct}%`, backlog_pct > 25 ? 'bad' : backlog_pct > 10 ? 'warn' : 'good'),
			trend_chip('CN blocked by parent', `${cn_block_pct}%`, cn_block_pct > 60 ? 'bad' : cn_block_pct > 30 ? 'warn' : 'good'),
			trend_chip('Hard failures', `${failure_pct}%`, failure_pct > 2 ? 'bad' : failure_pct > 0 ? 'warn' : 'good'),
			trend_chip('Recon gaps', fmt(gap_count), gap_count > 0 ? 'warn' : 'good'),
		].join(''));

		if (!channels.length) {
			$('#monitor-risk-channels').html('<div style="font-size:12px;color:#6c757d;">No guardrail channel data.</div>');
			return;
		}
		const ranked = channels.map(c => {
			const shipping_miss = Number(c.lines_shipping_tax_missing || 0);
			const vendor_miss = Number(c.lines_vendor_batch_missing || 0);
			const batch_hold = Number(c.order_rows_batch_hold || 0);
			const score = (shipping_miss * 3) + (vendor_miss * 2) + batch_hold;
			return { channel: c.channel || 'Unknown', score, shipping_miss, vendor_miss, batch_hold };
		}).sort((a, b) => b.score - a.score).slice(0, 6);
		const max_score = Math.max(...ranked.map(r => r.score), 1);
		$('#monitor-risk-channels').html(ranked.map(r => {
			const width = Math.max(4, Math.round((r.score / max_score) * 100));
			return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
				<div style="width:180px;font-size:12px;color:#334155;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(r.channel)}</div>
				<div style="flex:1;height:10px;background:#eef2f6;border-radius:6px;overflow:hidden;">
					<div style="height:100%;width:${width}%;background:${UI.red};border-radius:6px;"></div>
				</div>
				<div style="width:180px;text-align:right;font-size:11px;color:${UI.slate};">
					score ${fmt(r.score)} | ship ${fmt(r.shipping_miss)} | batch ${fmt(r.vendor_miss + r.batch_hold)}
				</div>
			</div>`;
		}).join(''));
	}

	function render_workers(last_runs) {
		if (!last_runs) return;
		$('#worker-runs').html(Object.entries(last_runs).map(([fn, info]) => {
			const label = fn.replace(/_/g,' ').replace(/\b\w/g, c => c.toUpperCase());
			const at = info.at ? frappe.datetime.prettyDate(info.at) : 'Never';
			const ok = info.status === 'Complete';
			return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
				<span style="width:8px;height:8px;border-radius:50%;background:${ok?'#28a745':'#adb5bd'};display:inline-block;flex-shrink:0;"></span>
				<span style="flex:1;color:#495057;">${esc(label)}</span>
				<span style="font-size:11px;color:#6c757d;">${esc(at)}</span>
			</div>`;
		}).join('') || '<div style="color:#6c757d;">No worker log data</div>');
	}

	function render_guardrails(guardrails) {
		const g = guardrails || {};
		MONITOR_STATE.guardrails = g;
		render_monitoring_panels();
		const rows = Array.isArray(g.channels) ? g.channels : [];
		const window_days = Number(g.window_days || 7);
		const status_list = Array.isArray(g.statuses) ? g.statuses : [];
		const status_label = status_list.length ? status_list.join(', ') : 'ALL';
		$('#guardrail-status').text(`Last ${window_days} days | Statuses: ${status_label}`);

		const total_orders = rows.reduce((acc, row) => acc + Number(row.orders || 0), 0);
		const total_shipping_lines = rows.reduce((acc, row) => acc + Number(row.lines_with_shipping_charge || 0), 0);
		const total_shipping_tax_missing = rows.reduce((acc, row) => acc + Number(row.lines_shipping_tax_missing || 0), 0);
		const total_vendor_batch_missing = rows.reduce((acc, row) => acc + Number(row.lines_vendor_batch_missing || 0), 0);
		const total_batch_hold_orders = rows.reduce((acc, row) => acc + Number(row.order_rows_batch_hold || 0), 0);

		const shipping_tax_missing_pct = total_shipping_lines > 0
			? Math.round((total_shipping_tax_missing / total_shipping_lines) * 100)
			: 0;

		$('#guardrail-summary').html(`
			${stat_card('Orders in Window', 'gr-orders', '#212529')}
			${stat_card('Shipping Tax Missing', 'gr-ship-tax', total_shipping_tax_missing > 0 ? '#dc3545' : '#28a745')}
			${stat_card('Vendor Batch Missing', 'gr-batch-miss', total_vendor_batch_missing > 0 ? '#fd7e14' : '#28a745')}
			${stat_card('Batch Hold Orders', 'gr-batch-hold', total_batch_hold_orders > 0 ? '#9b59b6' : '#28a745')}
		`);
		$('#gr-orders').text(fmt(total_orders));
		$('#gr-ship-tax').text(`${fmt(total_shipping_tax_missing)} (${shipping_tax_missing_pct}%)`);
		$('#gr-batch-miss').text(fmt(total_vendor_batch_missing));
		$('#gr-batch-hold').text(fmt(total_batch_hold_orders));

		if (!rows.length) {
			$('#guardrail-table-wrap').hide();
			return;
		}

		$('#guardrail-table-wrap').show();
		$('#guardrail-tbody').html(rows.map(row => {
			const shipTaxMissing = Number(row.lines_shipping_tax_missing || 0);
			const shipTaxPct = Number(row.shipping_tax_missing_pct || 0);
			const vendorBatchMissing = Number(row.lines_vendor_batch_missing || 0);
			const uniwareBatchMissing = Number(row.lines_uniware_batch_missing || 0);
			const batchHold = Number(row.order_rows_batch_hold || 0);
			return `<tr>
				<td style="font-weight:600;">${esc(row.channel || 'Unknown')}</td>
				<td style="text-align:right;">${fmt(row.orders)}</td>
				<td style="text-align:right;">${fmt(row.lines_with_shipping_charge)}</td>
				<td style="text-align:right;color:${shipTaxMissing > 0 ? '#dc3545' : '#28a745'};font-weight:600;">
					${fmt(shipTaxMissing)}${shipTaxMissing > 0 ? ` (${shipTaxPct}%)` : ''}
				</td>
				<td style="text-align:right;color:${vendorBatchMissing > 0 ? '#fd7e14' : '#28a745'};font-weight:600;">${fmt(vendorBatchMissing)}</td>
				<td style="text-align:right;color:${uniwareBatchMissing > 0 ? '#fd7e14' : '#28a745'};font-weight:600;">${fmt(uniwareBatchMissing)}</td>
				<td style="text-align:right;color:${batchHold > 0 ? '#9b59b6' : '#28a745'};font-weight:600;">${fmt(batchHold)}</td>
			</tr>`;
		}).join(''));
	}

	function current_guardrail_statuses() {
		const mode = ($(wrapper).find('#guardrail-filter').val() || 'active').trim();
		const map = {
			all: '',
			active: 'fetched,ready,batch_hold,failed',
			ready: 'ready',
			batch_hold: 'batch_hold',
			failed: 'failed,dead',
		};
		return map[mode] !== undefined ? map[mode] : map.active;
	}

	function get_guardrail_filter_mode() {
		return ($(wrapper).find('#guardrail-filter').val() || 'active').trim();
	}

	function set_guardrail_filter_mode(mode) {
		const value = (mode || 'active').trim();
		const allowed = new Set(['all', 'active', 'ready', 'batch_hold', 'failed']);
		const finalMode = allowed.has(value) ? value : 'active';
		$(wrapper).find('#guardrail-filter').val(finalMode);
	}

	function load_saved_guardrail_filter() {
		try {
			const saved = window.localStorage.getItem(GUARDRAIL_FILTER_KEY);
			if (saved) set_guardrail_filter_mode(saved);
		} catch (e) {
			// Ignore storage access errors (private mode / policy restrictions).
		}
	}

	function save_guardrail_filter() {
		try {
			window.localStorage.setItem(GUARDRAIL_FILTER_KEY, get_guardrail_filter_mode());
		} catch (e) {
			// Ignore storage write errors.
		}
	}

	function load_guardrails() {
		if (!acquire_request_lock('guardrails')) return;
		$('#guardrail-status').text('Loading…');
		frappe.call({
			method: API + '.ops_posting_guardrail_summary',
			args: { days: 14, statuses: current_guardrail_statuses() || null },
			freeze: false,
			callback: function (r) {
				release_request_lock('guardrails');
				if (!r.message) return;
				render_guardrails(r.message);
			},
			error: function () {
				release_request_lock('guardrails');
				$('#guardrail-status').html('<span style="color:#dc3545;">Failed to load</span>');
			},
		});
	}

	// ─── Fetch / Post Workers ────────────────────────────────────────────────

	const $fetch_log = $(wrapper).find('#fetch-log');
	const $post_log  = $(wrapper).find('#post-log');

	// Real-time progress events from fetch/post workers
	frappe.realtime.on('uc_ops_progress', function (data) {
		const worker = data.worker || '';
		const msg    = data.msg   || '';
		const level  = data.level || 'info';
		if (worker === 'fetch_orders' || worker === 'fetch_returns' || worker === 'promote_fetched_to_ready') {
			$fetch_log.show();
			log($fetch_log, msg, level);
			if (data.done) load_dashboard();
		} else if (worker === 'post_invoices' || worker === 'post_credit_notes') {
			$post_log.show();
			log($post_log, msg, level);
			if (data.done) load_dashboard();
		}
	});

	function update_fetch_mode_badge() {
		const from = $(wrapper).find('#fetch-from-date').val();
		const to   = $(wrapper).find('#fetch-to-date').val();
		const $badge = $(wrapper).find('#fetch-mode-badge');
		if (from && to) {
			$badge.css({ background: '#cce5ff', color: '#004085' }).text(`Mode: Date Range  ${from} → ${to}`);
		} else if (from) {
			$badge.css({ background: '#fff3cd', color: '#856404' }).text(`Mode: Date Range  ${from} → now`);
		} else {
			$badge.css({ background: '#e2e3e5', color: '#383d41' }).text('Mode: Cursor');
		}
	}
	$(wrapper).find('#fetch-from-date, #fetch-to-date').on('change', update_fetch_mode_badge);
	$(wrapper).find('#btn-fetch-clear-dates').on('click', function () {
		$(wrapper).find('#fetch-from-date').val('');
		$(wrapper).find('#fetch-to-date').val('');
		update_fetch_mode_badge();
	});

	$(wrapper).find('#btn-fetch-orders').on('click', function () {
		const $btn  = $(this);
		const from  = $(wrapper).find('#fetch-from-date').val();
		const to    = $(wrapper).find('#fetch-to-date').val();
		const explicit = Boolean(from);

		if (explicit) {
			// Date range mode — call ops_fetch_orders directly.
			const orig = $btn.text();
			$btn.prop('disabled', true).text('Running…');
			$fetch_log.show();
			log($fetch_log, `Starting fetch orders (${from} → ${to || 'now'})…`, 'info');
			frappe.call({
				method: API + '.ops_fetch_orders',
				args: { from_date: from, to_date: to || null },
				freeze: false,
				callback: function (r) {
					$btn.prop('disabled', false).text(orig);
					if (r.message) {
						if (r.message.enqueued) {
							log($fetch_log, r.message.message || 'Running in background — watch progress below.', 'info');
							frappe.show_alert({ message: 'Fetch orders started in background', indicator: 'blue' }, 5);
						} else {
							log_result($fetch_log, 'fetch_orders', r.message);
							if (r.message.ok) {
								frappe.show_alert({ message: 'Fetch orders completed', indicator: 'green' }, 5);
								load_dashboard();
							} else {
								frappe.show_alert({ message: 'Fetch orders failed', indicator: 'red' }, 6);
							}
						}
					}
				},
				error: function () {
					$btn.prop('disabled', false).text(orig);
					log($fetch_log, 'Request failed — check error log', 'error');
				},
			});
		} else {
			// Cursor mode — go through the standard run_worker path.
			run_worker('fetch_orders', $btn, $fetch_log);
		}
	});
	$(wrapper).find('#btn-promote-ready').on('click', function () { run_worker('promote_fetched_to_ready', $(this), $fetch_log); });
	function update_returns_mode_badge() {
		const from = $(wrapper).find('#returns-from-date').val();
		const to   = $(wrapper).find('#returns-to-date').val();
		const $badge = $(wrapper).find('#returns-mode-badge');
		if (from && to) {
			$badge.css({ background: '#cce5ff', color: '#004085' }).text(`Mode: Date Range  ${from} → ${to}`);
		} else if (from) {
			$badge.css({ background: '#fff3cd', color: '#856404' }).text(`Mode: Date Range  ${from} → now`);
		} else {
			$badge.css({ background: '#e2e3e5', color: '#383d41' }).text('Mode: Cursor');
		}
	}
	$(wrapper).find('#returns-from-date, #returns-to-date').on('change', update_returns_mode_badge);
	$(wrapper).find('#btn-returns-clear-dates').on('click', function () {
		$(wrapper).find('#returns-from-date').val('');
		$(wrapper).find('#returns-to-date').val('');
		update_returns_mode_badge();
	});

	$(wrapper).find('#btn-fetch-returns').on('click', function () {
		const $btn = $(this);
		const from = $(wrapper).find('#returns-from-date').val();
		const to   = $(wrapper).find('#returns-to-date').val();

		if (from) {
			// Date range mode
			const orig = $btn.text();
			$btn.prop('disabled', true).text('Running…');
			$fetch_log.show();
			log($fetch_log, `Starting fetch returns (${from} → ${to || 'now'})…`, 'info');
			frappe.call({
				method: API + '.ops_fetch_returns',
				args: { from_date: from, to_date: to || null },
				freeze: false,
				callback: function (r) {
					$btn.prop('disabled', false).text(orig);
					if (r.message) {
						if (r.message.enqueued) {
							log($fetch_log, r.message.message || 'Running in background — watch progress below.', 'info');
							frappe.show_alert({ message: 'Fetch returns started in background', indicator: 'blue' }, 5);
						} else {
							log_result($fetch_log, 'fetch_returns', r.message);
							if (r.message.ok) {
								frappe.show_alert({ message: 'Fetch returns completed', indicator: 'green' }, 5);
								load_dashboard();
							} else {
								frappe.show_alert({ message: 'Fetch returns failed', indicator: 'red' }, 6);
							}
						}
					}
				},
				error: function () {
					$btn.prop('disabled', false).text(orig);
					log($fetch_log, 'Request failed — check error log', 'error');
				},
			});
		} else {
			run_worker('fetch_returns', $btn, $fetch_log);
		}
	});
	function run_posting_worker(worker, $btn, range) {
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Running…');
		$post_log.show();
		log($post_log, `Starting ${worker.replace(/_/g, ' ')} for ${range.start_date} → ${range.end_date}…`, 'info');
		frappe.call({
			method: API + '.ops_run_worker',
			args: {
				worker: worker,
				start_date: range.start_date,
				end_date: range.end_date,
				limit: Number(range.per_pass_limit || 0) || undefined,
			},
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				if (r.message) {
					log_result($post_log, worker, r.message);
					if (r.message.queued) {
						frappe.show_alert({ message: `${worker.replace(/_/g, ' ')} queued — watch the stream above`, indicator: 'blue' }, 7);
					} else if (r.message.ok) {
						frappe.show_alert({ message: `${worker.replace(/_/g, ' ')} completed`, indicator: 'green' }, 5);
						load_dashboard();
					} else {
						frappe.show_alert({ message: `${worker.replace(/_/g, ' ')} failed`, indicator: 'red' }, 6);
					}
				}
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				log($post_log, 'Request failed — check error log', 'error');
			},
		});
	}

	$(wrapper).find('#btn-post-invoices').on('click', function () {
		const $btn = $(this);
		prompt_date_range(
			{
				title: 'Post Invoices — pick UC sale order date range',
				intro: 'Only UC sale orders whose order_date falls inside this window will be posted. Bounds are inclusive (YYYY-MM-DD). The preview below updates live as you change dates.',
				primary_action_label: 'Post Invoices',
				show_preview: true,
				include_posting_controls: true,
			},
			function (range) { run_posting_worker('post_invoices', $btn, range); }
		);
	});

	$(wrapper).find('#btn-post-cn').on('click', function () {
		const $btn = $(this);
		prompt_date_range(
			{
				title: 'Post Credit Notes — pick parent UC sale order date range',
				intro: 'Only credit notes whose parent UC sale order order_date falls inside this window will be posted. Bounds are inclusive.',
				primary_action_label: 'Post Credit Notes',
				show_preview: true,
				include_posting_controls: true,
			},
			function (range) { run_posting_worker('post_credit_notes', $btn, range); }
		);
	});

	$(wrapper).find('#btn-post-all').on('click', function () {
		const $btn = $(this);
		prompt_date_range(
			{
				title: 'Post All — pick UC sale order date range',
				intro: 'The selected date range applies to invoice <strong>and</strong> credit note posting only. (Other workers like GRN / inventory sync are not part of this button.) Bounds are inclusive.',
				primary_action_label: 'Post Invoices + Credit Notes',
				show_preview: true,
				include_posting_controls: true,
			},
			function (range) {
				frappe.confirm(
					`Drain posting for UC orders between <strong>${frappe.utils.escape_html(range.start_date)}</strong> and <strong>${frappe.utils.escape_html(range.end_date)}</strong>?<br><br>` +
					`Per pass limit: <strong>${fmt(range.per_pass_limit || 100)}</strong> · Max passes: <strong>${fmt(range.max_passes || 12)}</strong> · Max runtime: <strong>${fmt(range.max_runtime_mins || 20)} min</strong>`,
					function () {
						$post_log.show();
						$post_log.empty();
						$btn.prop('disabled', true).text('Running…');
						log($post_log, `Starting drain run for ${range.start_date} → ${range.end_date} (limit ${range.per_pass_limit || 100}, max passes ${range.max_passes || 12})…`, 'info');
						frappe.call({
							method: API + '.ops_post_all_until_settled',
							args: {
								start_date: range.start_date,
								end_date: range.end_date,
								per_pass_limit: Number(range.per_pass_limit || 100),
								max_passes: Number(range.max_passes || 12),
								max_runtime_mins: Number(range.max_runtime_mins || 20),
								include_credit_notes: 1,
							},
							freeze: false,
							callback: function (r) {
								const msg = r && r.message;
								if (msg && msg.ok) {
									const steps = Array.isArray(msg.progress) ? msg.progress : [];
									steps.forEach(p => {
										const inv = p.invoice || {};
										const cn = p.credit_note || {};
										log(
											$post_log,
											`Pass ${p.pass}: INV processed=${fmt(inv.ready_processed || 0)} posted=${fmt(inv.ready_posted || 0)} hold=${fmt(inv.ready_batch_hold || 0)} failed=${fmt(inv.ready_failed || 0)} reservation_conflict=${fmt(inv.reservation_conflicts || 0)} | CN processed=${fmt(cn.processed || 0)} posted=${fmt(cn.posted || 0)} deferred=${fmt(cn.deferred || 0)} | Ready now=${fmt((p.window_after || {}).ready || 0)}`,
											(p.progressed ? 'ok' : 'warn')
										);
									});
									const fin = msg.final_window || {};
									const stopHints = {
										window_drained: 'All in-flight rows in this window were drained.',
										no_progress: 'Stopped after repeated no-progress passes (likely stock/config blockers).',
										max_runtime_reached: 'Stopped by runtime cap to avoid long blocking runs.',
										max_passes_reached: 'Stopped by pass cap; increase Max passes if needed.',
									};
									log(
										$post_log,
										`Done: ${msg.stop_reason || 'completed'} · ${stopHints[msg.stop_reason] || 'Run finished.'} · elapsed=${fmt(msg.elapsed_s || 0)}s · passes=${fmt(msg.passes_run || 0)} · window ready=${fmt(((fin.pipeline_status || {}).ready) || 0)} fetched=${fmt(((fin.pipeline_status || {}).fetched) || 0)} verify=${fmt(((fin.pipeline_status || {}).verify) || 0)} batch_hold=${fmt(((fin.pipeline_status || {}).batch_hold) || 0)} posted=${fmt(fin.posted_count || 0)}`,
										'ok'
									);
									frappe.show_alert({ message: 'Post All drain completed', indicator: 'green' }, 6);
								} else {
									log_result($post_log, 'post_all', msg || { ok: false, error: 'Unknown error' });
									frappe.show_alert({ message: 'Post All drain failed', indicator: 'red' }, 6);
								}
								$btn.prop('disabled', false).text('Post All');
								load_dashboard();
							},
							error: function () {
								$btn.prop('disabled', false).text('Post All');
								log($post_log, 'Post All drain request failed', 'error');
							},
						});
					}
				);
			}
		);
	});

	// ─── Step 3 · Price mismatch audit + SAP invoice cancel ─────────────────
	(function init_price_audit_default_dates() {
		const to = frappe.datetime.get_today();
		const from = frappe.datetime.add_days(to, -14);
		const $f = $(wrapper).find('#audit-price-from');
		const $t = $(wrapper).find('#audit-price-to');
		if ($f.length && !$f.val()) $f.val(from);
		if ($t.length && !$t.val()) $t.val(to);
	})();

	function _parse_sap_cancel_ident(raw) {
		const s = String(raw || '').trim();
		if (!s) return { uc_order_name: null, doc_entry: null };
		if (/^\d+$/.test(s)) return { uc_order_name: null, doc_entry: s };
		return { uc_order_name: s, doc_entry: null };
	}

	$(wrapper).find('#btn-audit-price-mismatch').on('click', function () {
		const from_d = $(wrapper).find('#audit-price-from').val();
		const to_d = $(wrapper).find('#audit-price-to').val();
		const lim = parseInt($(wrapper).find('#audit-price-limit').val(), 10) || 200;
		const only_m = $(wrapper).find('#audit-price-only-mismatch').prop('checked') ? 1 : 0;
		if (!from_d || !to_d) {
			frappe.msgprint(__('Pick From and To dates for the audit.'));
			return;
		}
		$(wrapper).find('#audit-price-summary').text(__('Running audit…'));
		frappe.call({
			method: API + '.ops_price_mismatch_audit',
			args: { from_date: from_d, to_date: to_d, limit: lim, only_mismatched: only_m },
			freeze: true,
			callback: function (r) {
				const d = r.message || {};
				$(wrapper).find('#audit-price-summary').html(
					`${__('Scanned')} ${fmt(d.scanned || 0)} · <strong>${fmt(d.mismatch_count || 0)}</strong> ${__('mismatches')}`
					+ ` · ${__('skipped')} (${__('bundle / empty')}) ${fmt(d.skipped_bundle_or_empty || 0)}`
					+ ` · ${__('errors')} ${fmt(d.error_count || 0)}`
					+ (d.matched_count != null ? ` · ${__('matched')} ${fmt(d.matched_count)}` : '')
				);
				const rows = d.mismatches || [];
				if (!rows.length) {
					$(wrapper).find('#audit-price-table-wrap').hide();
					$(wrapper).find('#audit-price-tbody').empty();
					return;
				}
				$(wrapper).find('#audit-price-table-wrap').show();
				$(wrapper).find('#audit-price-tbody').html(rows.map(row => {
					const issues = (row.line_issues || []).map(i => {
						if (i.issue === 'unit_price') {
							return `${esc(i.item)}: SAP ${i.sap_unit} vs exp ${i.expected_unit} (Δ ${i.delta})`;
						}
						return `${esc(i.item)}: ${esc(i.issue)}`;
					}).join('; ');
					return `<tr>
						<td><code style="font-size:10px;">${esc(row.order)}</code></td>
						<td>${esc(row.channel || '')}</td>
						<td>${esc(row.sap_doc_num || '')} <span style="color:#6b7280;font-size:10px;">(${esc(String(row.sap_doc_entry || ''))})</span></td>
						<td style="text-align:right;">${Number(row.sap_doc_tax || 0).toFixed(2)}</td>
						<td style="text-align:right;">${Number(row.expected_doc_tax || 0).toFixed(2)}</td>
						<td style="color:${Number(row.tax_delta) > 0.01 ? '#b45309' : '#2563eb'};">${Number(row.tax_delta || 0).toFixed(2)}</td>
						<td style="max-width:380px;font-size:10px;">${issues || '—'}</td>
					</tr>`;
				}).join(''));
			},
			error: function () {
				$(wrapper).find('#audit-price-summary').text(__('Audit failed — see Error Log.'));
			},
		});
	});

	$(wrapper).find('#btn-sap-cancel-preview').on('click', function () {
		const ident = _parse_sap_cancel_ident($(wrapper).find('#sap-cancel-ident').val());
		const $pre = $(wrapper).find('#sap-cancel-preview-out');
		if (!ident.uc_order_name && !ident.doc_entry) {
			frappe.msgprint(__('Enter a UC order name or numeric SAP DocEntry.'));
			return;
		}
		frappe.call({
			method: API + '.ops_sap_cancel_ar_invoice',
			args: {
				uc_order_name: ident.uc_order_name,
				doc_entry: ident.doc_entry,
				confirm: 0,
				reset_pipeline: $(wrapper).find('#sap-cancel-reset').prop('checked') ? 1 : 0,
			},
			freeze: true,
			callback: function (r) {
				$pre.show().text(JSON.stringify(r.message, null, 2));
			},
		});
	});

	$(wrapper).find('#btn-sap-cancel-run').on('click', function () {
		const ident = _parse_sap_cancel_ident($(wrapper).find('#sap-cancel-ident').val());
		if (!ident.uc_order_name && !ident.doc_entry) {
			frappe.msgprint(__('Enter a UC order name or numeric SAP DocEntry.'));
			return;
		}
		frappe.confirm(
			__('Cancel this AR invoice in SAP B1? This posts to Service Layer Invoices(DocEntry)/Cancel. Continue?'),
			function () {
				frappe.call({
					method: API + '.ops_sap_cancel_ar_invoice',
					args: {
						uc_order_name: ident.uc_order_name,
						doc_entry: ident.doc_entry,
						confirm: 1,
						reset_pipeline: $(wrapper).find('#sap-cancel-reset').prop('checked') ? 1 : 0,
					},
					freeze: true,
					callback: function (r) {
						frappe.show_alert({ message: __('SAP cancel completed — see JSON below.'), indicator: 'green' }, 5);
						$(wrapper).find('#sap-cancel-preview-out').show().text(JSON.stringify(r.message, null, 2));
						load_dashboard();
					},
				});
			},
		);
	});

	// ─── Batch Validation ────────────────────────────────────────────────────

	// Keep the latest digest in memory so Copy / CSV export can reuse it
	let _shortage_digest_cache = [];

	function _digest_qty_needed(row) {
		// Pre-validate payload uses `total_needed`; legacy batch-hold path
		// may only carry `shortage` + `available`, so fall back gracefully.
		if (row.total_needed != null) return Number(row.total_needed);
		const short = Number(row.total_shortage || 0);
		const avail = Number(row.available || 0);
		return short + avail;
	}

	function _digest_qty_available(row) {
		if (row.available != null) return Number(row.available);
		const need = _digest_qty_needed(row);
		const short = Number(row.total_shortage || 0);
		return Math.max(0, need - short);
	}

	function _digest_orders_list(row) {
		const arr = Array.isArray(row.orders) ? row.orders : [];
		return arr.map(o => (typeof o === 'string') ? o : (o && o.name) || '').filter(Boolean);
	}

	function render_shortage_digest(digest) {
		_shortage_digest_cache = Array.isArray(digest) ? digest : [];
		if (!_shortage_digest_cache.length) {
			$(wrapper).find('#batch-shortage-digest').hide();
			$(wrapper).find('#btn-digest-create-gr').hide();
			return;
		}
		$(wrapper).find('#btn-digest-create-gr').toggle(IS_ADMIN);
		const total_short = _shortage_digest_cache.reduce((a, r) => a + Number(r.total_shortage || 0), 0);
		const total_orders_set = new Set();
		_shortage_digest_cache.forEach(r => _digest_orders_list(r).forEach(o => total_orders_set.add(o)));
		$(wrapper).find('#batch-digest-summary').text(
			`${_shortage_digest_cache.length} item · batch · warehouse combos · `
			+ `${total_short.toFixed(3)} units short · `
			+ `${total_orders_set.size || _shortage_digest_cache.reduce((a, r) => a + Number(r.order_count || 0), 0)} affected orders`
		);
		const html = _shortage_digest_cache.map(row => {
			const orders = _digest_orders_list(row);
			const need = _digest_qty_needed(row);
			const avail = _digest_qty_available(row);
			const short = Number(row.total_shortage || 0);
			const orders_cell = orders.length
				? `<span title="${esc(orders.join(', '))}" style="color:var(--muted);">${orders.slice(0, 3).map(o => esc(o)).join(', ')}${orders.length > 3 ? ` <em style="color:#6c757d;">+${orders.length - 3} more</em>` : ''}</span>`
				: '<span style="color:#adb5bd;">—</span>';
			const fefo_cell = row.fefo_rescuable
				? `<td style="text-align:center;" title="EC-FG has ${Number(row.ec_fg_total_qty || 0).toFixed(3)} units available across all batches — will auto-recover via FEFO"><span style="color:#28a745;font-weight:700;">✓</span> <span style="font-size:10px;color:#28a745;">${Number(row.ec_fg_total_qty || 0).toFixed(3)}</span></td>`
				: `<td style="text-align:center;color:#adb5bd;" title="EC-FG does not have enough stock for FEFO recovery">—</td>`;
			return `<tr>
				<td><strong>${esc(row.warehouse_code || '—')}</strong></td>
				<td style="font-family:var(--mono,monospace);">${esc(row.item_code || '—')}</td>
				<td style="font-family:var(--mono,monospace);">${esc(row.batch_number || '—')}</td>
				<td style="text-align:right;font-variant-numeric:tabular-nums;">${need.toFixed(3)}</td>
				<td style="text-align:right;font-variant-numeric:tabular-nums;color:#6c757d;">${avail.toFixed(3)}</td>
				<td style="text-align:right;font-variant-numeric:tabular-nums;color:#dc3545;font-weight:700;">${short.toFixed(3)}</td>
				${fefo_cell}
				<td style="text-align:right;">${fmt(row.order_count || orders.length || 0)}</td>
				<td style="font-size:11px;">${orders_cell}</td>
			</tr>`;
		}).join('');
		$(wrapper).find('#batch-digest-tbody').html(html);
		$(wrapper).find('#batch-shortage-digest').show();
	}

	function _build_digest_rows_for_export() {
		const header = ['Warehouse', 'Item Code', 'Batch', 'Qty Needed', 'Qty Available', 'Shortage', 'FEFO Rescuable', 'EC-FG Total Qty', 'Orders', 'Affected Order IDs'];
		const rows = _shortage_digest_cache.map(row => [
			row.warehouse_code || '',
			row.item_code || '',
			row.batch_number || '',
			_digest_qty_needed(row).toFixed(3),
			_digest_qty_available(row).toFixed(3),
			Number(row.total_shortage || 0).toFixed(3),
			row.fefo_rescuable ? 'Yes' : 'No',
			Number(row.ec_fg_total_qty || 0).toFixed(3),
			String(row.order_count || _digest_orders_list(row).length || 0),
			_digest_orders_list(row).join('; '),
		]);
		return [header, ...rows];
	}

	function copy_shortage_digest() {
		if (!_shortage_digest_cache.length) {
			frappe.show_alert({ message: __('No shortages to copy.'), indicator: 'orange' });
			return;
		}
		const tsv = _build_digest_rows_for_export().map(r => r.join('\t')).join('\n');
		const done = (ok) => frappe.show_alert({
			message: ok ? __('Shortage digest copied — paste into Excel / Sheets.') : __('Copy failed.'),
			indicator: ok ? 'green' : 'red',
		});
		if (navigator.clipboard && navigator.clipboard.writeText) {
			navigator.clipboard.writeText(tsv).then(() => done(true)).catch(() => done(false));
		} else {
			try {
				const ta = document.createElement('textarea');
				ta.value = tsv;
				document.body.appendChild(ta);
				ta.select();
				document.execCommand('copy');
				document.body.removeChild(ta);
				done(true);
			} catch (e) { done(false); }
		}
	}

	function download_shortage_digest_csv() {
		if (!_shortage_digest_cache.length) {
			frappe.show_alert({ message: __('No shortages to export.'), indicator: 'orange' });
			return;
		}
		const csv_escape = (v) => {
			const s = String(v == null ? '' : v);
			return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
		};
		const csv = _build_digest_rows_for_export().map(r => r.map(csv_escape).join(',')).join('\n');
		const blob = new Blob(["\ufeff" + csv], { type: 'text/csv;charset=utf-8;' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 16);
		a.href = url;
		a.download = `batch-shortages-${ts}.csv`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	function load_batch_status() {
		if (!acquire_request_lock('batch_status')) return;
		$(wrapper).find('#batch-summary').html('<span style="font-size:12px;color:#6c757d;">Loading…</span>');
		$(wrapper).find('#batch-prevalidate-result').hide();
		frappe.call({
			method: API + '.ops_batch_validation_summary',
			freeze: false,
			callback: function (r) {
				release_request_lock('batch_status');
				if (!r.message) return;
				const d = r.message;
				$(wrapper).find('#batch-summary').html(`
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Batch Hold</div>
						<div style="font-size:26px;font-weight:700;color:${d.batch_hold_count > 0 ? '#fd7e14' : '#28a745'};margin-top:4px;">${fmt(d.batch_hold_count)}</div>
					</div>
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Ready to Post</div>
						<div style="font-size:26px;font-weight:700;color:#0d6efd;margin-top:4px;">${fmt(d.ready_count)}</div>
					</div>
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Fetched (Pending)</div>
						<div style="font-size:26px;font-weight:700;color:#adb5bd;margin-top:4px;">${fmt(d.fetched_count)}</div>
					</div>`);

				render_shortage_digest(d.shortage_digest || []);

				const orders = d.batch_hold_orders || [];
				if (!orders.length) {
					$(wrapper).find('#batch-table-wrap').hide();
					$(wrapper).find('#batch-pagination').empty();
					return;
				}
				const total_pages = Math.max(1, Math.ceil(orders.length / BATCH_PAGE_SIZE));
				if (BATCH_PAGE > total_pages) BATCH_PAGE = total_pages;
				const start_idx = (BATCH_PAGE - 1) * BATCH_PAGE_SIZE;
				const paged_orders = orders.slice(start_idx, start_idx + BATCH_PAGE_SIZE);
				$(wrapper).find('#batch-table-wrap').show();
				$(wrapper).find('#batch-tbody').html(paged_orders.map(row => `<tr>
					<td><a href="/app/unicommerce-orders/${encodeURIComponent(row.name)}" target="_blank" style="color:#0d6efd;">${esc(row.uc_order_id || row.name)}</a></td>
					<td>${esc(row.channel || '—')}</td>
					<td>${esc(row.order_date || '—')}</td>
					<td style="color:#fd7e14;font-weight:600;">${esc(row.hold_age || '—')}</td>
					<td style="text-align:center;">${esc(row.attempt_count || 0)}</td>
					<td style="color:#6c757d;font-size:11px;max-width:240px;" title="${esc(row.last_error || '')}">${esc((row.last_error || '').substring(0, 100))}</td>
					<td>
						<button class="btn btn-default btn-xs uc-retry-btn"
							data-doctype="Unicommerce Orders" data-name="${esc(row.name)}" data-mode="queue" style="margin-right:4px;">Queue</button>
						<button class="btn btn-warning btn-xs uc-retry-btn"
							data-doctype="Unicommerce Orders" data-name="${esc(row.name)}" data-mode="now">Retry Now</button>
					</td>
				</tr>`).join(''));

				$(wrapper).find('#batch-tbody .uc-retry-btn').on('click', function () {
					const $b = $(this);
					retry($b.data('doctype'), $b.data('name'), $b.data('mode'), $b);
				});
				$(wrapper).find('#batch-pagination').html(`
					${page_size_selector('batch-page-size', BATCH_PAGE_SIZE)}
					<button class="btn btn-default btn-xs" id="btn-batch-prev" ${BATCH_PAGE <= 1 ? 'disabled' : ''}>Prev</button>
					<span style="font-size:12px;color:#64748b;">Page ${BATCH_PAGE} / ${total_pages} • ${fmt(orders.length)} rows</span>
					<button class="btn btn-default btn-xs" id="btn-batch-next" ${BATCH_PAGE >= total_pages ? 'disabled' : ''}>Next</button>
				`);
				$(wrapper).find('#batch-page-size').off('change').on('change', function () {
					BATCH_PAGE_SIZE = Number($(this).val() || 20);
					BATCH_PAGE = 1;
					try { window.localStorage.setItem(BATCH_PAGE_SIZE_KEY, String(BATCH_PAGE_SIZE)); } catch (e) {}
					load_batch_status();
				});
				$(wrapper).find('#btn-batch-prev').off('click').on('click', function () {
					if (BATCH_PAGE > 1) { BATCH_PAGE -= 1; load_batch_status(); }
				});
				$(wrapper).find('#btn-batch-next').off('click').on('click', function () {
					if (BATCH_PAGE < total_pages) { BATCH_PAGE += 1; load_batch_status(); }
				});
			},
			error: function () {
				release_request_lock('batch_status');
			},
		});
	}

	// ─── Returns Cross-Check ─────────────────────────────────────────────────

	function load_returns_summary() {
		if (!acquire_request_lock('returns_summary')) return;
		$('#returns-summary-cards').html('<span style="font-size:12px;color:#6c757d;">Loading…</span>');
		$('#returns-table-wrap').hide();
		frappe.call({
			method: API + '.ops_returns_summary',
			freeze: false,
			callback: function (r) {
				release_request_lock('returns_summary');
				if (!r.message) return;
				const d = r.message;
				const by_status = d.by_status || {};
				MONITOR_STATE.returns = d;
				render_monitoring_panels();

				$('#returns-summary-cards').html(`
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Total</div>
						<div style="font-size:26px;font-weight:700;color:#212529;margin-top:4px;">${fmt(d.total)}</div>
					</div>
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Posted</div>
						<div style="font-size:26px;font-weight:700;color:#28a745;margin-top:4px;">${fmt(by_status.posted||0)}</div>
					</div>
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Pending</div>
						<div style="font-size:26px;font-weight:700;color:#adb5bd;margin-top:4px;">${fmt(by_status.pending||0)}</div>
					</div>
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:160px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Parent Not Posted</div>
						<div style="font-size:26px;font-weight:700;color:${d.pending_parent_not_posted>0?'#fd7e14':'#28a745'};margin-top:4px;">${fmt(d.pending_parent_not_posted)}</div>
					</div>
					<div style="border:1px solid #e9ecef;border-radius:8px;padding:14px;background:#fff;min-width:130px;">
						<div style="font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#6c757d;font-weight:600;">Failed / Dead</div>
						<div style="font-size:26px;font-weight:700;color:${(by_status.failed||0)+(by_status.dead||0)>0?'#dc3545':'#28a745'};margin-top:4px;">${fmt((by_status.failed||0)+(by_status.dead||0))}</div>
					</div>
				`);

				const rows = d.rows || [];
				if (!rows.length) {
					$('#returns-table-wrap').hide();
					$('#returns-pagination').empty();
					return;
				}
				const filtered_rows = rows.filter(row => {
					const st = (row.status || '').toLowerCase();
					const pst = (row.parent_status || '').toLowerCase();
					if (CURRENT_CN_FILTER === 'all') return true;
					if (CURRENT_CN_FILTER === 'pending') return st === 'pending';
					if (CURRENT_CN_FILTER === 'failed') return st === 'failed' || st === 'dead';
					if (CURRENT_CN_FILTER === 'posted') return st === 'posted';
					if (CURRENT_CN_FILTER === 'blocked') return st === 'pending' && pst !== 'posted';
					return true;
				});
				const total_pages = Math.max(1, Math.ceil(filtered_rows.length / RETURNS_PAGE_SIZE));
				if (RETURNS_PAGE > total_pages) RETURNS_PAGE = total_pages;
				const start_idx = (RETURNS_PAGE - 1) * RETURNS_PAGE_SIZE;
				const paged_rows = filtered_rows.slice(start_idx, start_idx + RETURNS_PAGE_SIZE);
				$('#returns-table-wrap').show();
				$('#returns-tbody').html(paged_rows.map(row => {
					const cn_status = row.status || '';
					const parent_status = row.parent_status || '—';
					const blocked = cn_status === 'pending' && parent_status !== 'posted';
					return `<tr style="${blocked ? 'background:#fff8e1;' : ''}">
						<td style="white-space:nowrap;">
							<a href="/app/uc-credit-note-staging/${encodeURIComponent(row.name)}" target="_blank" style="color:#0d6efd;font-size:11px;">${esc(row.uc_return_id || row.name)}</a>
						</td>
						<td style="white-space:nowrap;">
							<a href="/app/unicommerce-orders/${encodeURIComponent(row.uc_order_id||'')}" target="_blank" style="color:#0d6efd;font-size:11px;">${esc(row.uc_order_id || '—')}</a>
						</td>
						<td style="white-space:nowrap;">${esc(row.return_date || '—')}</td>
						<td>${esc(row.return_type || '—')}</td>
						<td>${status_pill(cn_status)}</td>
						<td>${status_pill(parent_status)}</td>
						<td style="font-size:11px;color:#6c757d;">${esc(row.parent_sap_doc_entry || row.parent_sap_posted || '—')}</td>
						<td style="font-size:11px;color:${row.last_error?'#dc3545':'#6c757d'};max-width:240px;">${esc((row.last_error||'').substring(0,120))}</td>
						<td style="white-space:nowrap;">
							<button class="btn btn-default btn-xs uc-validate-cn-btn" data-uc-return-id="${esc(row.uc_return_id || '')}" style="margin-right:4px;">Validate</button>
							<button class="btn btn-warning btn-xs uc-retry-btn" data-doctype="UC Credit Note Staging" data-name="${esc(row.name)}" data-mode="now">Retry Now</button>
						</td>
					</tr>`;
				}).join(''));
				if (!filtered_rows.length) {
					$('#returns-tbody').html('<tr><td colspan="9" style="text-align:center;color:#6c757d;padding:18px;">No rows for current filter.</td></tr>');
				}
				$('#returns-pagination').html(`
					${page_size_selector('returns-page-size', RETURNS_PAGE_SIZE)}
					<button class="btn btn-default btn-xs" id="btn-returns-prev" ${RETURNS_PAGE <= 1 ? 'disabled' : ''}>Prev</button>
					<span style="font-size:12px;color:#64748b;">Page ${RETURNS_PAGE} / ${total_pages} • ${fmt(filtered_rows.length)} rows</span>
					<button class="btn btn-default btn-xs" id="btn-returns-next" ${RETURNS_PAGE >= total_pages ? 'disabled' : ''}>Next</button>
				`);
				$(wrapper).find('#returns-page-size').off('change').on('change', function () {
					RETURNS_PAGE_SIZE = Number($(this).val() || 20);
					RETURNS_PAGE = 1;
					try { window.localStorage.setItem(RETURNS_PAGE_SIZE_KEY, String(RETURNS_PAGE_SIZE)); } catch (e) {}
					load_returns_summary();
				});
				$(wrapper).find('#btn-returns-prev').off('click').on('click', function () { if (RETURNS_PAGE > 1) { RETURNS_PAGE -= 1; load_returns_summary(); } });
				$(wrapper).find('#btn-returns-next').off('click').on('click', function () { if (RETURNS_PAGE < total_pages) { RETURNS_PAGE += 1; load_returns_summary(); } });
				$(wrapper).find('#returns-tbody .uc-retry-btn').on('click', function () {
					const $b = $(this);
					retry($b.data('doctype'), $b.data('name'), $b.data('mode'), $b);
				});
				$('#returns-tbody .uc-validate-cn-btn').on('click', function () {
					const uc_return_id = ($(this).data('uc-return-id') || '').toString().trim();
					if (!uc_return_id) {
						frappe.show_alert({ message: 'Missing return id', indicator: 'orange' }, 4);
						return;
					}
					frappe.call({
						method: API + '.ops_validate_credit_note',
						args: { uc_return_id },
						freeze: false,
						callback: function (r) {
							const d = r.message || {};
							frappe.msgprint({
								title: `Validate CN: ${esc(uc_return_id)}`,
								indicator: Number(d.unresolved_items || 0) > 0 ? 'orange' : 'green',
								message: `
									<div style="font-size:12px;line-height:1.6;">
										<div><strong>CN Record:</strong> ${esc(d.record_name || '—')}</div>
										<div><strong>Parent Order:</strong> ${esc(d.parent_record || '—')}</div>
										<div><strong>Parent Status:</strong> ${esc(d.parent_status || '—')}</div>
										<div><strong>Parent SAP DocEntry:</strong> ${esc(d.parent_sap_doc_entry || '—')}</div>
										<div><strong>Items:</strong> ${esc(d.item_count || 0)} | <strong>Unresolved:</strong> ${esc(d.unresolved_items || 0)}</div>
									</div>
								`,
							});
						},
					});
				});
			},
			error: function () {
				release_request_lock('returns_summary');
			},
		});
	}

	$(wrapper).find('#btn-load-returns').on('click', load_returns_summary);
	function save_cn_filter() {
		try { window.localStorage.setItem(CN_FILTER_KEY, CURRENT_CN_FILTER); } catch (e) {}
	}
	function load_saved_cn_filter() {
		try {
			const saved = (window.localStorage.getItem(CN_FILTER_KEY) || '').trim();
			const allowed = new Set(['all', 'pending', 'failed', 'posted', 'blocked']);
			if (allowed.has(saved)) CURRENT_CN_FILTER = saved;
		} catch (e) {}
		$(wrapper).find('.uc-cn-filter').removeClass('active');
		$(wrapper).find(`.uc-cn-filter[data-cn-filter="${CURRENT_CN_FILTER}"]`).addClass('active');
	}
	function load_page_size_settings() {
		try {
			const f = Number(window.localStorage.getItem(FAILURES_PAGE_SIZE_KEY) || FAILURES_PAGE_SIZE);
			const r = Number(window.localStorage.getItem(RETURNS_PAGE_SIZE_KEY) || RETURNS_PAGE_SIZE);
			const q = Number(window.localStorage.getItem(RECON_PAGE_SIZE_KEY) || RECON_PAGE_SIZE);
			const b = Number(window.localStorage.getItem(BATCH_PAGE_SIZE_KEY) || BATCH_PAGE_SIZE);
			if ([10, 20, 50, 100].includes(f)) FAILURES_PAGE_SIZE = f;
			if ([10, 20, 50, 100].includes(r)) RETURNS_PAGE_SIZE = r;
			if ([10, 20, 50, 100].includes(q)) RECON_PAGE_SIZE = q;
			if ([10, 20, 50, 100].includes(b)) BATCH_PAGE_SIZE = b;
		} catch (e) {}
	}
	function save_gst_pivot_settings() {
		try {
			window.localStorage.setItem(GST_PIVOT_PREFS_KEY, JSON.stringify(GST_PIVOT_STATE));
		} catch (e) {}
	}
	function load_gst_pivot_settings() {
		try {
			const raw = window.localStorage.getItem(GST_PIVOT_PREFS_KEY) || '';
			const saved = raw ? JSON.parse(raw) : {};
			['uc', 'sap'].forEach(function (k) {
				const cur = GST_PIVOT_STATE[k] || {};
				const nxt = saved[k] || {};
				const top = Number(nxt.top_n);
				const seriesValues = Array.isArray(nxt.series_values)
					? nxt.series_values.map(v => String(v || '').trim().toUpperCase()).filter(Boolean)
					: (cur.series_values || []);
				GST_PIVOT_STATE[k] = {
					sort_by: typeof nxt.sort_by === 'string' && nxt.sort_by ? nxt.sort_by : cur.sort_by,
					top_n: [0, 5, 10, 20, 50, 100].includes(top) ? top : cur.top_n,
					series_values: seriesValues,
				};
			});
		} catch (e) {}
	}
	$(wrapper).on('click', '.uc-cn-filter', function () {
		CURRENT_CN_FILTER = (($(this).data('cn-filter') || 'all') + '').trim();
		RETURNS_PAGE = 1;
		$(wrapper).find('.uc-cn-filter').removeClass('active');
		$(this).addClass('active');
		save_cn_filter();
		load_returns_summary();
	});
	$(wrapper).find('#btn-retry-failed-cn-now').on('click', function () {
		retry_cn_rows(
			row => (row.status || '').toLowerCase() === 'failed',
			'Retrying all failed credit notes now…'
		);
	});
	$(wrapper).find('#btn-retry-pending-cn-ready-parent').on('click', function () {
		retry_cn_rows(
			row => (row.status || '').toLowerCase() === 'pending' && (row.parent_status || '').toLowerCase() === 'posted',
			'Retrying pending credit notes where parent is posted…'
		);
	});

	function retry_cn_rows(predicate, start_message) {
		frappe.call({
			method: API + '.ops_returns_summary',
			args: { limit: 500 },
			freeze: false,
			callback: function (r) {
				const rows = (r.message && r.message.rows) || [];
				const targets = rows.filter(predicate || (() => false));
				if (!targets.length) {
					frappe.show_alert({ message: 'No matching credit notes found for retry', indicator: 'orange' }, 5);
					return;
				}

				let progress_html = `
					<div style="font-size:12px;line-height:1.7;">
						<div><strong>Total:</strong> ${targets.length}</div>
						<div><strong>Processed:</strong> <span id="cn-progress-done">0</span></div>
						<div><strong>Posted:</strong> <span id="cn-progress-posted" style="color:#15803d;font-weight:700;">0</span></div>
						<div><strong>Queued:</strong> <span id="cn-progress-queued" style="color:#1d4ed8;font-weight:700;">0</span></div>
						<div><strong>Failed:</strong> <span id="cn-progress-failed" style="color:#b91c1c;font-weight:700;">0</span></div>
					</div>
				`;
				frappe.msgprint({
					title: 'Bulk CN Retry Progress',
					message: progress_html,
					indicator: 'blue',
				});
				frappe.show_alert({ message: `${start_message} (${targets.length})`, indicator: 'blue' }, 5);
				let idx = 0;
				let posted = 0;
				let queued = 0;
				let failed = 0;
				const update_progress = () => {
					$('#cn-progress-done').text(idx);
					$('#cn-progress-posted').text(posted);
					$('#cn-progress-queued').text(queued);
					$('#cn-progress-failed').text(failed);
				};

				const run_next = () => {
					if (idx >= targets.length) {
						frappe.show_alert({
							message: `CN retry complete — posted: ${posted}, queued: ${queued}, failed: ${failed}`,
							indicator: failed ? 'orange' : 'green',
						}, 8);
						update_progress();
						load_returns_summary();
						load_dashboard();
						return;
					}
					const row = targets[idx++];
					frappe.call({
						method: API + '.ops_retry',
						args: {
							doctype: 'UC Credit Note Staging',
							name: row.name,
							mode: 'now',
						},
						freeze: false,
						callback: function (rr) {
							const res = rr.message || {};
							if (res.outcome === 'posted') posted += 1;
							else if (res.queued) queued += 1;
							else failed += 1;
							update_progress();
							run_next();
						},
						error: function () {
							failed += 1;
							update_progress();
							run_next();
						},
					});
				};

				run_next();
			},
		});
	}

	$(wrapper).find('#btn-debug-uc-returns').on('click', function () {
		const $btn = $(this);
		const _today = frappe.datetime.get_today();
		const from = $(wrapper).find('#returns-from-date').val() || frappe.datetime.add_days(_today, -14);
		const to   = $(wrapper).find('#returns-to-date').val()   || _today;
		$btn.prop('disabled', true).text('Probing…');
		frappe.call({
			method: API + '.ops_debug_uc_returns',
			args: { from_date: from, to_date: to },
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text('Debug UC Returns API');
				if (!r.message) return;
				const d = r.message;
				let html = `<strong>Facility codes:</strong> ${esc(JSON.stringify(d.facility))}<br>`;
				html += `<strong>Date sent:</strong> ${esc(d.from_uc)} → ${esc(d.to_uc)}<br><br>`;
				(d.variants || []).forEach(v => {
					const ok = v.status === 200;
					const color = ok ? '#28a745' : '#dc3545';
					html += `<div style="margin-bottom:10px;padding:8px;border:1px solid ${color};border-radius:4px;font-size:12px;">`;
					html += `<strong style="color:${color};">[${v.status}] ${esc(v.label)}</strong><br>`;
					html += `<em>Sent:</em> <code>${esc(JSON.stringify(v.body_sent))}</code><br>`;
					html += `<em>Response:</em> <code>${esc(v.response)}</code>`;
					html += `</div>`;
				});
				frappe.msgprint({ title: 'UC Returns API Debug', message: html, indicator: 'blue' });
			},
		});
	});
	$(wrapper).find('#btn-load-batch').on('click', load_batch_status);
	$(wrapper).find('#btn-digest-copy').on('click', copy_shortage_digest);
	$(wrapper).find('#btn-digest-csv').on('click', download_shortage_digest_csv);
	$(wrapper).find('#btn-digest-create-gr').on('click', function () {
		if (!_shortage_digest_cache.length) {
			frappe.msgprint('No shortage data. Run Pre-Validate first.');
			return;
		}
		// Build human-readable summary for confirmation
		const lines = _shortage_digest_cache.map(r =>
			`${esc(r.warehouse_code)} · ${esc(r.item_code)} · ${esc(r.batch_number)} — ${Number(r.total_shortage||0).toFixed(3)} units`
		);
		const preview = lines.slice(0, 10).join('<br>') + (lines.length > 10 ? `<br><em>+${lines.length - 10} more</em>` : '');
		frappe.confirm(
			`<strong>Create a Goods Receipt in SAP B1</strong> for <strong>${_shortage_digest_cache.length}</strong> shorted item/batch/warehouse combos?<br><br>`
			+ `<div style="font-size:11px;color:#475569;max-height:180px;overflow:auto;border:1px solid #e2e8f0;border-radius:6px;padding:8px;">${preview}</div><br>`
			+ `<strong>Qty added = shortage qty</strong> for each line. DocDate = today. System Manager action.`,
			function () {
				const $btn = $(wrapper).find('#btn-digest-create-gr');
				const orig = $btn.text();
				$btn.prop('disabled', true).text('Creating…');
				const shortages = _shortage_digest_cache.map(r => ({
					item_code: r.item_code || '',
					batch_number: r.batch_number || '',
					warehouse_code: r.warehouse_code || '',
					quantity: Number(r.total_shortage || 0),
				})).filter(r => r.item_code && r.batch_number && r.warehouse_code && r.quantity > 0);
				frappe.call({
					method: API + '.ops_create_gr_from_shortages',
					args: { shortages_json: JSON.stringify(shortages) },
					freeze: false,
					callback: function (r) {
						$btn.prop('disabled', false).text(orig);
						const d = r && r.message;
						if (d && d.ok) {
							frappe.show_alert({ message: d.message, indicator: 'green' }, 8);
						} else {
							frappe.msgprint({ title: 'GR Creation Failed', message: (d && d.error) || 'Unknown error', indicator: 'red' });
						}
					},
					error: function () {
						$btn.prop('disabled', false).text(orig);
						frappe.show_alert({ message: 'Request failed — check Error Log', indicator: 'red' }, 5);
					},
				});
			}
		);
	});

	// ─── EC-FG FEFO Fallback toggle ─────────────────────────────────────────

	function fefo_render_btn(enabled) {
		const $btn = $(wrapper).find('#btn-fefo-toggle');
		if (enabled) {
			$btn.text('FEFO Fallback: ON')
				.removeClass('btn-default').addClass('btn-success');
		} else {
			$btn.text('FEFO Fallback: OFF')
				.removeClass('btn-success').addClass('btn-default');
		}
		$btn.data('fefo-enabled', enabled ? 1 : 0);
	}

	function fefo_load_status() {
		if (!IS_ADMIN) return;
		frappe.call({
			method: API + '.ops_get_fefo_fallback_status',
			callback: function (r) {
				if (r && r.message) fefo_render_btn(r.message.enabled);
			},
		});
	}

	$(wrapper).find('#btn-fefo-toggle').on('click', function () {
		if (!IS_ADMIN) {
			frappe.show_alert({ message: 'System Manager role required', indicator: 'red' }, 4);
			return;
		}
		const $btn = $(this);
		const current = Number($btn.data('fefo-enabled') || 0);
		const next = current ? 0 : 1;
		$btn.prop('disabled', true);
		frappe.call({
			method: API + '.ops_set_fefo_fallback',
			args: { enabled: next },
			callback: function (r) {
				$btn.prop('disabled', false);
				if (r && r.message) {
					fefo_render_btn(r.message.enabled);
					frappe.show_alert({
						message: r.message.message || (r.message.enabled ? 'FEFO Fallback enabled' : 'FEFO Fallback disabled'),
						indicator: r.message.enabled ? 'green' : 'orange',
					}, 4);
				}
			},
			error: function () {
				$btn.prop('disabled', false);
				frappe.show_alert({ message: 'Failed to update FEFO setting', indicator: 'red' }, 5);
			},
		});
	});

	fefo_load_status();

	// ───────────────────────────────────────────────────────────────────────
	// Pre-Validate Ready Orders (async with live progress)
	//
	// The backend dry-run can take 30s–3min on realistic operator volumes
	// (100 ready orders × 3–5 SAP round-trips each). Instead of blocking on
	// one long HTTP call, we enqueue the job, then poll status every 1.5s
	// and render a live progress bar. Reloads mid-run automatically
	// reattach to the in-flight job via `prevalidate_attach_if_running()`.
	// ───────────────────────────────────────────────────────────────────────
	const PREVALIDATE_POLL_MS = 1500;
	let PREVALIDATE_POLL_TIMER = null;
	let PREVALIDATE_BTN_ORIGINAL_TEXT = null;

	function fmt_duration_s(total_s) {
		const s = Math.max(0, Math.round(Number(total_s) || 0));
		if (s < 60) return `${s}s`;
		const m = Math.floor(s / 60);
		const rem = s % 60;
		return rem ? `${m}m ${rem}s` : `${m}m`;
	}

	function prevalidate_render_progress(snap) {
		const $box = $(wrapper).find('#batch-prevalidate-progress');
		const p = (snap && snap.progress) || {};
		const status = String((snap && snap.status) || 'idle').toLowerCase();
		const stage = String(p.stage || status);
		const done = Number(p.done || 0);
		const total = p.total == null ? null : Number(p.total);
		const percent = Math.max(0, Math.min(100, Number(p.percent || 0)));

		const stage_labels = {
			queued: 'Queued — waiting for a worker…',
			starting: 'Starting…',
			prewarming_sap_cache: 'Bulk-fetching batch stock from SAP…',
			validating: total != null ? `Validating order ${done} of ${total}` : `Validating order ${done}`,
			finished: 'Finished',
			cancelled: 'Cancelled',
		};
		$box.find('#batch-prevalidate-progress-label').text(stage_labels[stage] || stage);

		const counter = total != null ? `${fmt(done)} / ${fmt(total)} · ${percent}%` : `${fmt(done)} checked`;
		$box.find('#batch-prevalidate-progress-counter').text(counter);
		$box.find('#batch-prevalidate-progress-bar').css('width', percent + '%');

		const meta_parts = [];
		if (p.elapsed_s != null) meta_parts.push(`elapsed ${fmt_duration_s(p.elapsed_s)}`);
		if (p.eta_s != null && stage !== 'finished' && stage !== 'cancelled') {
			meta_parts.push(`~${fmt_duration_s(p.eta_s)} remaining`);
		}
		if (p.current_order) meta_parts.push(`current: <code>${frappe.utils.escape_html(p.current_order)}</code>`);
		if (p.ok_count || p.would_hold) {
			meta_parts.push(`<span style="color:var(--ok,#16a34a);">✓ ${fmt(p.ok_count || 0)} OK</span>`);
			if (p.would_hold) meta_parts.push(`<span style="color:var(--warn,#dc3545);">⚠ ${fmt(p.would_hold)} would hold</span>`);
		}
		$box.find('#batch-prevalidate-progress-meta').html(meta_parts.join(' · '));

		$box.show();
	}

	function prevalidate_render_final(snap) {
		const d = (snap && snap.result) || {};
		const $btn = $(wrapper).find('#btn-prevalidate-batches');
		$btn.prop('disabled', false);
		if (PREVALIDATE_BTN_ORIGINAL_TEXT) $btn.text(PREVALIDATE_BTN_ORIGINAL_TEXT);

		const status = String((snap && snap.status) || 'done').toLowerCase();
		if (status === 'cancelled') {
			$(wrapper).find('#batch-prevalidate-result')
				.css({ background: '#fff7ed', border: '1px solid #d97706', color: '#b45309' })
				.html(`⏸ <strong>Pre-validate cancelled</strong> after checking ${fmt(d.checked || 0)} orders.`)
				.show();
			return;
		}
		if (status === 'error') {
			const err = snap && snap.error ? String(snap.error) : 'unknown error';
			$(wrapper).find('#batch-prevalidate-result')
				.css({ background: '#fff5f5', border: '1px solid #dc3545', color: '#991b1b' })
				.html(`⚠️ <strong>Pre-validate failed:</strong> ${frappe.utils.escape_html(err)} — check Error Log.`)
				.show();
			return;
		}

		const color = d.would_hold > 0 ? '#dc3545' : '#28a745';
		const bgColor = d.would_hold > 0 ? '#fff5f5' : '#f0fff4';
		const icon = d.would_hold > 0 ? '⚠️' : '✅';

		const f = d.filters || (snap && snap.filters) || {};
		const range_bits = [];
		if (f.from_date || f.to_date) {
			range_bits.push(`<strong>${esc(f.from_date || '…')}</strong> → <strong>${esc(f.to_date || '…')}</strong>`);
		}
		if (Array.isArray(f.statuses) && f.statuses.length) {
			range_bits.push(`scope: <code>${esc(f.statuses.join(', '))}</code>`);
		}
		const range_line = range_bits.length
			? `<div style="font-size:11px;color:#6c757d;margin-top:4px;">${range_bits.join(' · ')}</div>`
			: '';

		const scope_label = (Array.isArray(f.statuses) && f.statuses.length === 1 && f.statuses[0] === 'ready')
			? 'ready'
			: (Array.isArray(f.statuses) ? f.statuses.join('/') : 'scoped');

		$(wrapper).find('#batch-prevalidate-result')
			.css({ background: bgColor, border: `1px solid ${color}`, color: color })
			.html(
				`${icon} <strong>Pre-Validate · ${fmt(d.checked || 0)} ${esc(scope_label)} orders checked</strong> — `
				+ `<span style="color:#28a745;">${fmt(d.ok_count || 0)} can post</span>, `
				+ `<span style="color:#dc3545;"><strong>${fmt(d.would_hold || 0)}</strong> would go to batch_hold</span>.`
				+ range_line
			)
			.show();
		render_shortage_digest(d.shortages || []);

		// Auto-expand and scroll to the shortage digest so the operator
		// immediately sees which items are missing stock. No-op if there
		// are no shortages (the table stays hidden via render_shortage_digest).
		if ((d.shortages || []).length) {
			setTimeout(() => {
				const $digest = $(wrapper).find('#batch-shortage-digest:visible');
				if ($digest.length) {
					const target = $digest.offset().top - 80;
					$('html, body').animate({ scrollTop: target }, 400);
				}
			}, 250);
		}
	}

	function prevalidate_stop_polling() {
		if (PREVALIDATE_POLL_TIMER) {
			clearTimeout(PREVALIDATE_POLL_TIMER);
			PREVALIDATE_POLL_TIMER = null;
		}
	}

	function prevalidate_poll_once() {
		frappe.call({
			method: API + '.ops_prevalidate_batches_status',
			freeze: false,
			callback: function (r) {
				const snap = (r && r.message) || {};
				const status = String(snap.status || 'idle').toLowerCase();
				if (status === 'idle') {
					prevalidate_stop_polling();
					$(wrapper).find('#batch-prevalidate-progress').hide();
					const $btn = $(wrapper).find('#btn-prevalidate-batches');
					$btn.prop('disabled', false);
					if (PREVALIDATE_BTN_ORIGINAL_TEXT) $btn.text(PREVALIDATE_BTN_ORIGINAL_TEXT);
					return;
				}
				prevalidate_render_progress(snap);
				if (status === 'queued' || status === 'running') {
					PREVALIDATE_POLL_TIMER = setTimeout(prevalidate_poll_once, PREVALIDATE_POLL_MS);
					return;
				}
				// Terminal — done / cancelled / error
				prevalidate_stop_polling();
				prevalidate_render_final(snap);
			},
			error: function () {
				// Transient network hiccup — keep polling so we don't give up
				// on a job that's still running.
				PREVALIDATE_POLL_TIMER = setTimeout(prevalidate_poll_once, PREVALIDATE_POLL_MS * 2);
			},
		});
	}

	function prevalidate_start_polling() {
		prevalidate_stop_polling();
		prevalidate_poll_once();
	}

	function prevalidate_attach_if_running() {
		// On page load, reattach the UI to a job already running in the
		// background OR restore the last completed result so results don't
		// vanish on page refresh.
		frappe.call({
			method: API + '.ops_prevalidate_batches_status',
			freeze: false,
			callback: function (r) {
				const snap = (r && r.message) || {};
				const status = String(snap.status || 'idle').toLowerCase();
				if (status === 'queued' || status === 'running') {
					const $btn = $(wrapper).find('#btn-prevalidate-batches');
					if (!PREVALIDATE_BTN_ORIGINAL_TEXT) PREVALIDATE_BTN_ORIGINAL_TEXT = $btn.text();
					$btn.prop('disabled', true).text('Checking…');
					$(wrapper).find('#batch-prevalidate-result').hide();
					prevalidate_render_progress(snap);
					prevalidate_start_polling();
				} else if (status === 'done' || status === 'cancelled' || status === 'error') {
					// Restore last result so the shortage digest persists across refreshes.
					prevalidate_render_final(snap);
				}
			},
		});
	}

	function _prevalidate_submit(args) {
		const $btn = $(wrapper).find('#btn-prevalidate-batches');
		if (!PREVALIDATE_BTN_ORIGINAL_TEXT) PREVALIDATE_BTN_ORIGINAL_TEXT = $btn.text();
		$btn.prop('disabled', true).text('Checking…');
		$(wrapper).find('#batch-prevalidate-result').hide();
		$(wrapper).find('#batch-shortage-digest').hide();
		prevalidate_render_progress({ status: 'queued', progress: { stage: 'queued', done: 0, total: null, percent: 0, elapsed_s: 0 } });
		frappe.call({
			method: API + '.ops_prevalidate_batches_run_async',
			args: args,
			freeze: false,
			callback: function (r) {
				const snap = (r && r.message) || {};
				if (String(snap.status || '').toLowerCase() === 'already_running') {
					frappe.show_alert({
						message: 'A pre-validate run is already in progress — watching it now.',
						indicator: 'blue',
					}, 4);
				}
				prevalidate_start_polling();
			},
			error: function () {
				$btn.prop('disabled', false).text(PREVALIDATE_BTN_ORIGINAL_TEXT || 'Pre-Validate Ready Orders');
				$(wrapper).find('#batch-prevalidate-progress').hide();
				frappe.show_alert({ message: 'Could not queue pre-validate — check Error Log', indicator: 'red' }, 5);
			},
		});
	}

	function _open_prevalidate_dialog() {
		const today = frappe.datetime.get_today();
		const week_ago = frappe.datetime.add_days(today, -7);

		const d = new frappe.ui.Dialog({
			title: __('Pre-Validate Orders · Date Range'),
			size: 'small',
			fields: [
				{
					fieldtype: 'HTML', fieldname: 'intro',
					options: `<div style="font-size:12px;color:#6c757d;margin-bottom:6px;">
						Validate orders in the selected date range against live SAP batch stock.
						The run will report how many <strong style="color:#28a745;">can post</strong>
						vs. how many <strong style="color:#dc3545;">would go to batch_hold</strong>,
						plus the exact item · batch · warehouse shortages.
					</div>`,
				},
				{
					fieldtype: 'Date', fieldname: 'from_date', label: __('From Date'),
					default: week_ago, reqd: 1,
				},
				{
					fieldtype: 'Column Break',
				},
				{
					fieldtype: 'Date', fieldname: 'to_date', label: __('To Date'),
					default: today, reqd: 1,
				},
				{ fieldtype: 'Section Break' },
				{
					fieldtype: 'MultiCheck', fieldname: 'statuses', label: __('Pipeline Status Scope'),
					columns: 2,
					options: [
						{ label: 'Ready', value: 'ready', checked: 1 },
						{ label: 'Batch Hold', value: 'batch_hold', checked: 0 },
						{ label: 'Fetched (pending)', value: 'fetched', checked: 0 },
						{ label: 'Failed', value: 'failed', checked: 0 },
					],
				},
				{
					fieldtype: 'Int', fieldname: 'limit', label: __('Max Orders'),
					default: 0,
					description: __('0 = no cap (recommended for full date-range sweep). Use a small number for a quick probe.'),
				},
			],
			primary_action_label: __('Validate'),
			primary_action: function (values) {
				const from_date = values.from_date;
				const to_date = values.to_date;
				if (!from_date || !to_date) {
					frappe.msgprint(__('Please pick both From and To dates.'));
					return;
				}
				if (from_date > to_date) {
					frappe.msgprint(__('From Date cannot be after To Date.'));
					return;
				}
				let statuses = values.statuses;
				if (Array.isArray(statuses)) statuses = statuses.filter(Boolean);
				if (!statuses || !statuses.length) statuses = ['ready'];
				d.hide();
				_prevalidate_submit({
					from_date: from_date,
					to_date: to_date,
					statuses: statuses,
					limit: Number(values.limit) || 0,
				});
			},
		});
		d.show();
	}

	$(wrapper).find('#btn-prevalidate-batches').on('click', _open_prevalidate_dialog);

	$(wrapper).find('#btn-prevalidate-cancel').on('click', function () {
		const $btn = $(this);
		$btn.prop('disabled', true).text('Cancelling…');
		frappe.call({
			method: API + '.ops_prevalidate_batches_cancel',
			freeze: false,
			callback: function () {
				$btn.prop('disabled', false).text('Cancel');
				frappe.show_alert({ message: 'Cancellation requested — will stop after the current order.', indicator: 'orange' }, 4);
			},
			error: function () {
				$btn.prop('disabled', false).text('Cancel');
			},
		});
	});

	$(wrapper).find('#btn-retry-batch-holds').on('click', function () {
		const $btn = $(this);
		frappe.confirm(
			'<strong>Emergency release:</strong> Move all <em>batch_hold</em> orders back to <em>ready</em>, <strong>bypassing the 30-minute cooldown</strong>?<br><br>' +
			'Auto-recovery normally handles this inside each <em>Post Invoices</em> cycle. Use this only after you have confirmed fresh stock is available in SAP. ' +
			'Each released order still counts toward the hold-cap, so orders that repeatedly fail validation will eventually escalate to <em>dead</em>.',
			() => {
				run_worker('retry_batch_holds', $btn, $fetch_log);
				setTimeout(() => { load_batch_status(); }, 1500);
			},
		);
	});

	$(wrapper).find('#btn-validate-order').on('click', function () {
		const val = $(wrapper).find('#batch-validate-input').val().trim();
		if (!val) { frappe.show_alert({ message: 'Enter a UC Order ID or record name', indicator: 'orange' }, 4); return; }
		frappe.show_alert({ message: 'Validating…', indicator: 'blue' });
		frappe.call({
			method: API + '.ops_validate_order',
			args: { uc_order_id: val },
			freeze: false,
			callback: function (r) {
				if (!r.message) return;
				const v = r.message;
				const batch = v.batch_check || {};
				const shortages = batch.missing || [];
				const batch_ok  = batch.ok !== false;

				function row_line(label, val_str, color) {
					return `<div style="display:flex;gap:8px;margin-bottom:4px;font-size:12px;">
						<span style="width:180px;color:#6c757d;flex-shrink:0;">${label}</span>
						<span style="font-weight:600;color:${color||'#212529'};">${val_str}</span>
					</div>`;
				}

				let shortage_html = '';
				if (shortages.length) {
					shortage_html = `<div style="margin-top:10px;padding:10px;background:#f8d7da;border-radius:6px;">
						<div style="font-size:12px;font-weight:700;color:#721c24;margin-bottom:6px;">Batch Shortages:</div>
						${shortages.map(s => `<div style="font-size:11px;color:#721c24;">
							${frappe.utils.escape_html(s.item_code)} / batch ${frappe.utils.escape_html(s.batch_number)}
							in ${frappe.utils.escape_html(s.warehouse_code)}:
							need ${s.qty_needed}, available ${s.qty_available}
						</div>`).join('')}
					</div>`;
				}

				frappe.msgprint({
					title: `Validate: ${frappe.utils.escape_html(v.uc_order_id || val)}`,
					indicator: (v.ready_for_invoice && batch_ok && v.payload_ok) ? 'green' : 'red',
					message: `<div style="margin-top:4px;">
						${row_line('Status', v.status, v.status === 'posted' ? '#28a745' : '#212529')}
						${row_line('Channel', v.channel || '—')}
						${row_line('Ready for invoice', v.ready_for_invoice ? 'Yes' : ('No — ' + (v.readiness_reason||'')), v.ready_for_invoice ? '#28a745' : '#dc3545')}
						${row_line('Batch check', batch_ok ? 'OK' : `${shortages.length} shortage(s)`, batch_ok ? '#28a745' : '#dc3545')}
						${row_line('Payload build', v.payload_ok ? `OK (${v.line_count} lines)` : 'FAILED', v.payload_ok ? '#28a745' : '#dc3545')}
						${v.payload_error ? `<div style="font-size:11px;color:#dc3545;margin-top:4px;">${frappe.utils.escape_html(v.payload_error)}</div>` : ''}
						${shortage_html}
					</div>`,
				});
			},
			error: function () {
				frappe.show_alert({ message: 'Validation failed — order not found or server error', indicator: 'red' }, 5);
			},
		});
	});

	// ─── Order Coverage ──────────────────────────────────────────────────────
	// Renders the ``ops_order_coverage_summary`` payload: table-wide totals
	// (not time-boxed), Uniware vs pipeline status bars, and the per-channel
	// matrix (Complete / Posted / Not Posted / Fetched / Ready / Held).
	// Kept separate from load_analytics because analytics is posted-only
	// and date-filtered — coverage is a "what's in the table right now"
	// sanity check answering the question "why does the list view show
	// 1555 COMPLETE orders but Ops Center shows fewer?".

	function load_coverage() {
		if (!acquire_request_lock('coverage')) return;
		$('#coverage-status').text('Loading…');
		$('#cov-channel-tbody').html(
			'<tr><td colspan="11" style="text-align:center;color:var(--text-muted);padding:16px;">Loading…</td></tr>'
		);
		frappe.call({
			method: API + '.ops_order_coverage_summary',
			freeze: false,
			callback: function (r) {
				release_request_lock('coverage');
				if (!r.message) return;
				render_coverage(r.message);
			},
			error: function () {
				release_request_lock('coverage');
				$('#coverage-status').text('Load failed.');
			},
		});
	}

	function render_coverage(d) {
		const total = Number(d.total_orders || 0);

		$('#cov-total').text(fmt(total));
		$('#cov-complete').text(fmt(d.complete_count));
		$('#cov-cancelled').text(fmt(d.cancelled_count));
		$('#cov-posted').text(fmt(d.posted_count));
		$('#cov-not-posted').text(fmt(d.not_posted_count));
		$('#cov-never').text(fmt(d.never_attempted));

		const pipeline_color = {
			fetched: '#adb5bd', pending: '#adb5bd', batch_hold: '#9b59b6',
			ready: '#0d6efd', posting: '#fd7e14', verify: '#17a2b8',
			posted: '#28a745', failed: '#dc3545', dead: '#7f0000', other: '#6c757d',
		};
		const pipeline_rows = Object.entries(d.pipeline_status || {})
			.filter(([, c]) => Number(c || 0) > 0)
			.sort((a, b) => Number(b[1]) - Number(a[1]));
		$('#cov-pipeline-bars').html(pipeline_rows.length ? pipeline_rows.map(([s, c]) => {
			const w = pct(Number(c || 0), total);
			const color = pipeline_color[s] || '#adb5bd';
			return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
				<div style="width:88px;font-size:12px;color:#495057;flex-shrink:0;text-transform:capitalize;">${esc(s)}</div>
				<div style="flex:1;height:12px;background:#f3f4f6;border-radius:4px;overflow:hidden;">
					<div style="width:${w}%;height:100%;background:${color};border-radius:4px;"></div>
				</div>
				<div style="width:110px;text-align:right;font-size:12px;font-weight:600;">${fmt(c)} <span style="color:#6c757d;font-weight:400;">(${w}%)</span></div>
			</div>`;
		}).join('') : '<div style="font-size:12px;color:var(--text-muted);">No orders.</div>');

		const uniware_color = {
			COMPLETE: '#28a745', CANCELLED: '#6c757d', PROCESSING: '#fd7e14',
			PENDING_VERIFICATION: '#17a2b8', CREATED: '#0d6efd',
		};
		const uniware_rows = Object.entries(d.uniware_status || {})
			.filter(([, c]) => Number(c || 0) > 0)
			.sort((a, b) => Number(b[1]) - Number(a[1]))
			.slice(0, 10);
		$('#cov-uniware-bars').html(uniware_rows.length ? uniware_rows.map(([s, c]) => {
			const w = pct(Number(c || 0), total);
			const key = String(s).toUpperCase();
			const color = uniware_color[key] || '#adb5bd';
			return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
				<div style="width:170px;font-size:12px;color:#495057;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(s)}">${esc(s)}</div>
				<div style="flex:1;height:12px;background:#f3f4f6;border-radius:4px;overflow:hidden;">
					<div style="width:${w}%;height:100%;background:${color};border-radius:4px;"></div>
				</div>
				<div style="width:110px;text-align:right;font-size:12px;font-weight:600;">${fmt(c)} <span style="color:#6c757d;font-weight:400;">(${w}%)</span></div>
			</div>`;
		}).join('') : '<div style="font-size:12px;color:var(--text-muted);">No orders.</div>');

		const channels = d.channels || [];
		if (!channels.length) {
			$('#cov-channel-tbody').html(
				'<tr><td colspan="11" style="text-align:center;color:var(--text-muted);padding:16px;">No data.</td></tr>'
			);
		} else {
			$('#cov-channel-tbody').html(channels.map(row => {
				const share = Number(row.posted_pct || 0);
				const share_color = share >= 75 ? '#28a745' : share >= 40 ? '#0d6efd' : share >= 15 ? '#fd7e14' : '#dc3545';
				const not_posted_color = Number(row.not_posted || 0) > 0 ? '#fd7e14' : '#6c757d';
				const fail_color = Number(row.failed || 0) + Number(row.dead || 0) > 0 ? '#dc3545' : '#6c757d';
				return `<tr>
					<td style="font-weight:600;">${esc(row.channel || 'Unknown')}</td>
					<td style="text-align:right;">${fmt(row.total)}</td>
					<td style="text-align:right;color:#28a745;">${fmt(row.complete)}</td>
					<td style="text-align:right;color:var(--accent);font-weight:600;">${fmt(row.posted)}</td>
					<td style="text-align:right;color:${not_posted_color};">${fmt(row.not_posted)}</td>
					<td style="text-align:right;color:#6c757d;">${fmt(row.fetched)}</td>
					<td style="text-align:right;color:#0d6efd;">${fmt(row.ready)}</td>
					<td style="text-align:right;color:#9b59b6;">${fmt(row.batch_hold)}</td>
					<td style="text-align:right;color:${Number(row.failed||0) > 0 ? '#dc3545' : '#6c757d'};">${fmt(row.failed)}</td>
					<td style="text-align:right;color:${Number(row.dead||0) > 0 ? '#7f0000' : '#6c757d'};">${fmt(row.dead)}</td>
					<td>
						<div style="display:flex;align-items:center;gap:6px;">
							<div style="flex:1;height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden;">
								<div style="width:${share}%;height:100%;background:${share_color};border-radius:4px;"></div>
							</div>
							<span style="font-size:11px;color:#6c757d;width:40px;text-align:right;">${share.toFixed(1)}%</span>
						</div>
					</td>
				</tr>`;
			}).join(''));
		}

		$('#coverage-status').text(
			`${fmt(total)} total orders · ${fmt(d.complete_count)} COMPLETE · ${fmt(d.posted_count)} posted · `
			+ `${fmt(d.not_posted_count)} not posted · updated ${new Date().toLocaleTimeString()}`
		);
	}

	// ─── Analytics ───────────────────────────────────────────────────────────

	function load_analytics() {
		if (!acquire_request_lock('analytics')) return;
		const start = $(wrapper).find('#analytics-start').val();
		const end   = $(wrapper).find('#analytics-end').val();
		if (!start || !end) {
			release_request_lock('analytics');
			frappe.msgprint('Please set a date range.');
			return;
		}

		$('#analytics-status').text('Loading analytics…');
		$('#channel-tbody').html('<tr><td colspan="5" style="text-align:center;color:#6c757d;padding:16px;">Loading…</td></tr>');

		frappe.call({
			method: API + '.ops_channel_summary',
			args: { start_date: start, end_date: end },
			freeze: false,
			callback: function (r) {
				release_request_lock('analytics');
				if (!r.message) return;
				render_analytics(r.message);
			},
			error: function () {
				release_request_lock('analytics');
			},
		});
	}

	function render_analytics(d) {
		const total = d.total || {}, igst = d.igst || {}, cgst = d.cgst_sgst || {};

		$('#a-total-inv').text(fmt(total.cnt));
		$('#a-total-cn').text(fmt(d.cn_total));
		$('#a-total-tax').text(money(total.tax_total));
		$('#a-igst-cnt').text(fmt(igst.cnt));
		$('#a-igst-tax').text(money(igst.tax_total));
		$('#a-cgst-cnt').text(fmt(cgst.cnt));
		$('#a-cgst-tax').text(money(cgst.tax_total));

		// Tax type bar chart
		const total_cnt = Number(total.cnt || 0);
		$('#tax-type-bars').html([
			{ label: 'IGST (Inter-state)',        cnt: igst.cnt,  color: '#0d6efd' },
			{ label: 'CGST+SGST (Intra-state KA)', cnt: cgst.cnt, color: '#6f42c1' },
		].map(row => {
			const w = pct(Number(row.cnt||0), total_cnt);
			return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
				<div style="width:190px;font-size:12px;color:#495057;flex-shrink:0;">${row.label}</div>
				<div style="flex:1;height:14px;background:#f3f4f6;border-radius:4px;overflow:hidden;">
					<div style="width:${w}%;height:100%;background:${row.color};border-radius:4px;"></div>
				</div>
				<div style="width:90px;text-align:right;font-size:12px;font-weight:600;">${fmt(row.cnt)} <span style="color:#6c757d;font-weight:400;">(${w}%)</span></div>
			</div>`;
		}).join(''));

		// Channel table
		const channels = d.by_channel || [];
		if (!channels.length) {
			$('#channel-tbody').html('<tr><td colspan="5" style="text-align:center;color:#6c757d;padding:16px;">No posted orders in this date range.</td></tr>');
		} else {
			$('#channel-tbody').html(channels.map(row => {
				const share_pct = pct(Number(row.cnt||0), total_cnt);
				return `<tr>
					<td style="font-weight:600;">${esc(row.channel || 'Unknown')}</td>
					<td style="text-align:right;">${fmt(row.cnt)}</td>
					<td style="text-align:right;font-weight:600;">${money(row.tax_total)}</td>
					<td style="text-align:right;color:${Number(row.gap_count||0) > 0 ? '#dc3545' : '#28a745'};">${fmt(row.gap_count)}</td>
					<td>
						<div style="display:flex;align-items:center;gap:6px;">
							<div style="flex:1;height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden;">
								<div style="width:${share_pct}%;height:100%;background:#0d6efd;border-radius:4px;"></div>
							</div>
							<span style="font-size:11px;color:#6c757d;width:32px;text-align:right;">${share_pct}%</span>
						</div>
					</td>
				</tr>`;
			}).join(''));
		}

		const end = $(wrapper).find('#analytics-end').val();
		const start = $(wrapper).find('#analytics-start').val();
		$('#analytics-status').text(`${start} to ${end} — ${fmt(total.cnt)} invoices | Total tax: ${money(total.tax_total)}`);
	}

	function set_analytics_range(start, end) {
		$(wrapper).find('#analytics-start').val(start);
		$(wrapper).find('#analytics-end').val(end);
		load_analytics();
	}

	function month_range(offset) {
		const today = new Date();
		const first = new Date(today.getFullYear(), today.getMonth() + offset, 1);
		const last  = new Date(today.getFullYear(), today.getMonth() + offset + 1, 0);
		const fmt_d = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
		return { start: fmt_d(first), end: fmt_d(last) };
	}

	$(wrapper).find('#btn-analytics-load').on('click', load_analytics);
	$(wrapper).find('#btn-analytics-this-month').on('click', () => { const r = month_range(0);  set_analytics_range(r.start, r.end); });
	$(wrapper).find('#btn-analytics-prev-month').on('click', () => { const r = month_range(-1); set_analytics_range(r.start, r.end); });

	// ─── Lazy loaders for wizard steps + drawers ────────────────────────────
	// The old outer tab-bar was replaced by the wizard stepper (for
	// posting-related views) and a pair of <details> drawers (for triage and
	// "more tools"). Each surface lazy-loads its data the first time it's
	// opened so we don't hammer the backend with everything on page load.

	function reset_tab_scoped_paginators() {
		FAILURES_PAGE = 1;
		RETURNS_PAGE = 1;
		RECON_GAPS_PAGE = 1;
		RECON_GRN_PAGE = 1;
		RECON_INV_PAGE = 1;
		GST_SIDE_BY_SIDE_PAGE = 1;
		PER_ORDER_PAGE = 1;
		BATCH_PAGE = 1;
	}

	// When the user opens the Failures drawer, fetch the latest list once.
	$(wrapper).find('#drawer-failures').on('toggle', function () {
		if (!this.open) return;
		reset_tab_scoped_paginators();
		if (!$(wrapper).find('#failures-tbody').data('loaded')) load_failures();
	});

	// The "More Tools" drawer aggregates activity, monitoring, pipeline
	// detail, guardrails, returns cross-check and analytics. Only Activity
	// and Returns are safe to auto-load; the others require an explicit
	// click (to avoid surprise long-running calls).
	$(wrapper).find('#drawer-more').on('toggle', function () {
		if (!this.open) return;
		if (!$(wrapper).find('#activity-jobs').data('loaded')) load_activity();
	});

	// ─── Failures ─────────────────────────────────────────────────────────────

	function load_failures() {
		if (!acquire_request_lock('failures')) return;
		const stage = $(wrapper).find('#failures-stage-filter').val() || 'all';
		$(wrapper).find('#failures-tbody').html('<tr><td colspan="8" style="text-align:center;color:#6c757d;padding:20px;">Loading…</td></tr>');
		frappe.call({
			method: API + '.ops_failures',
			args: { stage: stage, page: FAILURES_PAGE, page_size: FAILURES_PAGE_SIZE },
			freeze: false,
			callback: function (r) {
				release_request_lock('failures');
				if (r.message) render_failures(r.message.rows || [], r.message);
			},
			error: function () {
				release_request_lock('failures');
				$(wrapper).find('#failures-tbody').html('<tr><td colspan="8" style="text-align:center;color:#dc3545;padding:20px;">Failed to load — check error log</td></tr>');
			},
		});
	}

	function render_failures(rows, meta) {
		const $tbody = $(wrapper).find('#failures-tbody');
		// Use server-provided totals (not page-local counts) so the health score
		// is accurate even when paginated.
		MONITOR_STATE.failures = {
			total: Number((meta && meta.total_count) !== undefined ? meta.total_count : rows.length),
			hard: Number((meta && meta.hard_count) !== undefined ? meta.hard_count :
				(Array.isArray(rows) ? rows.filter(r => (r.status || '').toLowerCase() === 'dead').length : 0)),
		};
		render_monitoring_panels();
		if (!rows.length) {
			$tbody.html('<tr><td colspan="8" style="text-align:center;color:#28a745;padding:28px;font-weight:600;">✓ No failures — pipeline is healthy!</td></tr>');
			$('#failures-pagination').empty();
			return;
		}
		$tbody.html(rows.map(r => {
			const ext_link = `<a href="/app/${r.doctype.toLowerCase().replace(/ /g,'-')}/${encodeURIComponent(r.name)}" target="_blank" style="color:#0d6efd;text-decoration:none;font-weight:500;">${esc(r.external_id || r.name)}</a>`;
			const err_short = (r.last_error || '').substring(0, 90);
			const err_html = r.last_error ? `<span title="${esc(r.last_error)}" style="color:#6c757d;cursor:help;">${esc(err_short)}${r.last_error.length > 90 ? '…' : ''}</span>` : '<span style="color:#adb5bd;">—</span>';
			return `<tr>
				<td style="text-align:center;">
					<input type="checkbox" class="uc-failure-select" data-doctype="${esc(r.doctype)}" data-name="${esc(r.name)}" />
				</td>
				<td>${stage_badge(r.stage)}</td>
				<td>${ext_link}</td>
				<td>${status_pill(r.status)}</td>
				<td style="text-align:center;">${r.attempt_count !== null && r.attempt_count !== undefined ? r.attempt_count : '—'}</td>
				<td style="max-width:240px;">${err_html}</td>
				<td style="color:#6c757d;">${esc(r.modified ? frappe.datetime.prettyDate(r.modified) : '—')}</td>
				<td style="white-space:nowrap;">
					<button class="btn btn-default btn-xs uc-retry-btn" data-doctype="${esc(r.doctype)}" data-name="${esc(r.name)}" data-mode="queue" style="margin-right:4px;">Queue</button>
					<button class="btn btn-warning btn-xs uc-retry-btn" data-doctype="${esc(r.doctype)}" data-name="${esc(r.name)}" data-mode="now">Retry Now</button>
				</td>
			</tr>`;
		}).join(''));
		$(wrapper).find('.uc-retry-btn').on('click', function () {
			const $b = $(this);
			retry($b.data('doctype'), $b.data('name'), $b.data('mode'), $b);
		});
		$(wrapper).find('.uc-failure-select').on('change', refresh_failure_selection_state);
		refresh_failure_selection_state();
		const current_page = Number((meta && meta.page) || FAILURES_PAGE || 1);
		const has_next = rows.length >= FAILURES_PAGE_SIZE;
		$('#failures-pagination').html(`
			${page_size_selector('failures-page-size', FAILURES_PAGE_SIZE)}
			<button class="btn btn-default btn-xs" id="btn-failures-prev" ${current_page <= 1 ? 'disabled' : ''}>Prev</button>
			<span style="font-size:12px;color:#64748b;">Page ${current_page}${has_next ? '+' : ''}</span>
			<button class="btn btn-default btn-xs" id="btn-failures-next" ${!has_next ? 'disabled' : ''}>Next</button>
		`);
		$(wrapper).find('#failures-page-size').off('change').on('change', function () {
			FAILURES_PAGE_SIZE = Number($(this).val() || 25);
			FAILURES_PAGE = 1;
			try { window.localStorage.setItem(FAILURES_PAGE_SIZE_KEY, String(FAILURES_PAGE_SIZE)); } catch (e) {}
			load_failures();
		});
		$(wrapper).find('#btn-failures-prev').off('click').on('click', function () {
			if (FAILURES_PAGE > 1) { FAILURES_PAGE -= 1; load_failures(); }
		});
		$(wrapper).find('#btn-failures-next').off('click').on('click', function () {
			if (has_next) { FAILURES_PAGE += 1; load_failures(); }
		});
	}

	function selected_failure_rows() {
		const rows = [];
		$(wrapper).find('.uc-failure-select:checked').each(function () {
			const $c = $(this);
			rows.push({
				doctype: ($c.data('doctype') || '').toString(),
				name: ($c.data('name') || '').toString(),
			});
		});
		return rows;
	}

	function run_failure_bulk_retry(mode) {
		const rows = selected_failure_rows();
		if (!rows.length) {
			frappe.show_alert({ message: 'Select at least one failure row', indicator: 'orange' }, 4);
			return;
		}
		let idx = 0;
		let ok = 0;
		let failed = 0;
		const run_next = () => {
			if (idx >= rows.length) {
				frappe.show_alert({
					message: `Bulk retry (${mode}) complete — success: ${ok}, failed: ${failed}`,
					indicator: failed ? 'orange' : 'green',
				}, 8);
				load_failures();
				load_dashboard();
				return;
			}
			const row = rows[idx++];
			frappe.call({
				method: API + '.ops_retry',
				args: { doctype: row.doctype, name: row.name, mode },
				freeze: false,
				callback: function (r) {
					const res = r.message || {};
					if (res.queued || res.outcome === 'posted' || res.outcome === 'batch_hold' || res.outcome === 'ready') ok += 1;
					else failed += 1;
					run_next();
				},
				error: function () {
					failed += 1;
					run_next();
				},
			});
		};
		run_next();
	}

	function refresh_failure_selection_state() {
		const selected = selected_failure_rows().length;
		$('#failures-selected-count').text(`Selected: ${selected}`);
		const $checks = $(wrapper).find('.uc-failure-select');
		const all_checked = $checks.length > 0 && $checks.length === $checks.filter(':checked').length;
		$('#btn-failures-select-all').text(all_checked ? 'Unselect All' : 'Select All');
	}

	function retry(doctype, name, mode, $btn) {
		const orig = $btn.text();
		$btn.prop('disabled', true).text(mode === 'now' ? 'Running…' : 'Queuing…');
		frappe.call({
			method: API + '.ops_retry',
			args: { doctype, name, mode },
			freeze: mode === 'now',
			freeze_message: 'Executing retry…',
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				if (r.message) {
					const res = r.message;
					if (res.queued) frappe.show_alert({ message: name + ' queued for retry', indicator: 'blue' }, 5);
					else if (res.outcome === 'posted') frappe.show_alert({ message: name + ' posted successfully', indicator: 'green' }, 5);
					else frappe.show_alert({ message: `${name}: ${res.outcome || 'done'}${res.error ? ' — ' + res.error.substring(0,60) : ''}`, indicator: res.outcome === 'failed' ? 'red' : 'blue' }, 6);
					setTimeout(load_failures, 600);
				}
			},
			error: function () { $btn.prop('disabled', false).text(orig); frappe.show_alert({ message: 'Retry failed', indicator: 'red' }); },
		});
	}

	// ─── Activity ─────────────────────────────────────────────────────────────

	function load_activity() {
		$(wrapper).find('#activity-jobs').html('<div style="color:#6c757d;">Loading…</div>');
		$(wrapper).find('#activity-errors').text('Loading…');
		frappe.call({
			method: API + '.ops_activity',
			args: { hours: 24 },
			freeze: false,
			callback: function (r) {
				if (r.message) render_activity(r.message);
				$(wrapper).find('#activity-jobs').data('loaded', true);
			},
		});
	}

	function render_activity(data) {
		const jobs = data.jobs || [];
		const $jobs = $(wrapper).find('#activity-jobs');
		if (!jobs.length) {
			$jobs.html('<div style="color:#6c757d;font-size:12px;">No scheduled job logs in the last 24 hours.</div>');
		} else {
			$jobs.html(jobs.map(j => {
				const ok = j.status === 'Complete';
				const fn = (j.scheduled_job_type || '').split('.').pop();
				return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:12px;">
					<span style="width:8px;height:8px;border-radius:50%;background:${ok?'#28a745':'#dc3545'};display:inline-block;flex-shrink:0;"></span>
					<span style="flex:1;color:#495057;text-transform:capitalize;">${esc(fn.replace(/_/g,' '))}</span>
					<span style="background:${ok?'#d4edda':'#f8d7da'};color:${ok?'#155724':'#721c24'};padding:1px 7px;border-radius:10px;font-size:10px;font-weight:600;">${esc(j.status)}</span>
					<span style="font-size:11px;color:#6c757d;">${esc(frappe.datetime.prettyDate(j.creation))}</span>
				</div>`;
			}).join(''));
		}

		const $err = $(wrapper).find('#activity-errors');
		$err.empty();
		const errors = data.errors || [];
		if (!errors.length) $err.append('<div style="color:#6b7280;font-size:12px;">No errors in the last 24 hours.</div>');
		else errors.forEach(e => log($err, `[${frappe.datetime.prettyDate(e.creation)}] ${(e.method||'').split('.').pop()}: ${(e.error||'').substring(0,120)}`, 'error'));
	}

	// ─── Reconciliation ───────────────────────────────────────────────────────

	function load_reconciliation() {
		if (!acquire_request_lock('reconciliation')) return;
		$(wrapper).find('#recon-invoice-gaps, #recon-grn-drift, #recon-inv-drift')
			.html('<div style="color:#6c757d;font-size:12px;padding:8px 0;">Loading…</div>');
		const mode = $(wrapper).find('#recon-mode').val() || 'frappe';
		const method = mode === 'live'
			? (API + '.ops_reconciliation_live_sap')
			: (API + '.ops_reconciliation_frappe_snapshot');
		frappe.call({
			method,
			freeze: false,
			callback: function (r) {
				release_request_lock('reconciliation');
				if (r.message) render_reconciliation(r.message);
				load_gst_recon_status();
				load_transfer_summary();
				$(wrapper).find('#recon-invoice-gaps').data('loaded', true);
			},
			error: function () {
				release_request_lock('reconciliation');
			},
		});
	}
	// ─── Simple date-range reconciliation ──────────────────────────────────
	$(wrapper).find('#btn-recon-run-simple').on('click', function () {
		const $btn = $(this);
		const from = $(wrapper).find('#recon-range-from').val();
		const to   = $(wrapper).find('#recon-range-to').val();
		if (!from || !to) { frappe.msgprint('Pick both From and To dates.'); return; }
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Checking…');
		frappe.call({
			method: API + '.ops_recon_for_range',
			args: { from_date: from, to_date: to },
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				const d = r && r.message;
				if (!d || !d.ok) {
					frappe.show_alert({ message: (d && d.error) || 'Reconciliation failed', indicator: 'red' }, 5);
					return;
				}
				_render_simple_recon(d);
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				frappe.show_alert({ message: 'Request failed', indicator: 'red' }, 5);
			},
		});
	});

	function _render_simple_recon(d) {
		const $box = $(wrapper).find('#recon-simple-result');
		const STATUS_LABEL = {
			posted:'Posted to SAP', ready:'Ready (pending post)', fetched:'Fetched',
			batch_hold:'Batch Hold', failed:'Failed', dead:'Dead',
			posting:'Posting (in progress)', verify:'Verify', pending:'Pending',
		};
		const STATUS_COLOR = {
			posted:'#16a34a', ready:'#2563eb', fetched:'#64748b',
			batch_hold:'#d97706', failed:'#dc2626', dead:'#7f1d1d',
			posting:'#7c3aed', verify:'#0284c7', pending:'#94a3b8',
		};
		const total = d.total_orders || 0;
		const posted = d.posted_count || 0;
		const not_posted = d.not_posted_count || 0;
		const mismatches = d.price_mismatches_count || 0;

		// Summary chips
		const chip = (label, val, color) =>
			`<div style="padding:12px 16px;border-radius:8px;border:1px solid ${color}20;background:${color}10;min-width:120px;text-align:center;">
				<div style="font-size:22px;font-weight:700;color:${color};">${fmt(val)}</div>
				<div style="font-size:11px;color:#64748b;margin-top:2px;">${esc(label)}</div>
			</div>`;

		let html = `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;">
			${chip('Total Orders', total, '#64748b')}
			${chip('Posted to SAP', posted, '#16a34a')}
			${chip('Not Posted', not_posted, not_posted ? '#dc2626' : '#64748b')}
			${chip('Price Mismatch', mismatches, mismatches ? '#d97706' : '#64748b')}
		</div>`;

		// Not posted breakdown
		if ((d.not_posted_reasons || []).length) {
			html += `<div style="margin-bottom:12px;">
				<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#64748b;margin-bottom:6px;">Not Posted — Reasons</div>
				<table class="table table-bordered" style="font-size:12px;margin:0;">
					<thead><tr><th>Status</th><th>Reason</th><th style="text-align:right;">Count</th></tr></thead>
					<tbody>
						${(d.not_posted_reasons || []).map(r =>
							`<tr>
								<td><span style="color:${STATUS_COLOR[r.status]||'#64748b'};font-weight:600;">${esc(STATUS_LABEL[r.status]||r.status)}</span></td>
								<td style="color:#475569;">${esc(r.reason || '—')}</td>
								<td style="text-align:right;font-weight:600;">${fmt(r.count)}</td>
							</tr>`
						).join('')}
					</tbody>
				</table>
			</div>`;
		}

		// Credit note summary
		const cn = d.credit_note_summary || {};
		if (Object.keys(cn).length) {
			html += `<div style="margin-bottom:12px;font-size:12px;">
				<span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#64748b;margin-right:8px;">Credit Notes:</span>
				${Object.entries(cn).map(([s,c]) => `<span style="background:#f1f5f9;padding:2px 8px;border-radius:999px;margin-right:6px;">${esc(s)}: <strong>${fmt(c)}</strong></span>`).join('')}
			</div>`;
		}

		// Price mismatches
		if ((d.price_mismatches || []).length) {
			html += `<div style="margin-bottom:8px;">
				<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#d97706;margin-bottom:6px;">Price / Tax Mismatches (posted orders with diff > ₹1)</div>
				<div style="overflow:auto;max-height:220px;">
					<table class="table table-bordered" style="font-size:12px;margin:0;">
						<thead><tr><th>Order</th><th>Channel</th><th>SAP Doc</th><th style="text-align:right;">Tax Diff</th><th style="text-align:right;">Price Diff</th></tr></thead>
						<tbody>
							${(d.price_mismatches || []).map(m =>
								`<tr>
									<td><a href="/app/unicommerce-orders/${encodeURIComponent(m.order)}" target="_blank">${esc(m.order)}</a></td>
									<td>${esc(m.channel||'—')}</td>
									<td>${esc(m.sap_doc||'—')}</td>
									<td style="text-align:right;color:#dc2626;">₹${fmt(Math.round(m.tax_diff*100)/100)}</td>
									<td style="text-align:right;color:#dc2626;">₹${fmt(Math.round(m.price_diff*100)/100)}</td>
								</tr>`
							).join('')}
						</tbody>
					</table>
				</div>
			</div>`;
		} else if (posted > 0) {
			html += `<div style="color:#16a34a;font-size:12px;font-weight:600;">✓ All posted orders have matching prices (diff ≤ ₹1)</div>`;
		}

		$box.show().html(html);
	}

	// ─── Finance Reconciliation ───────────────────────────────────────────
	(function () {
		let _fin_data = null;          // last server response
		let _fin_all_rows = [];        // all order_rows from last run
		let _fin_page = 0;
		const FIN_PAGE_SIZE = 50;

		// Set default dates (last 30 days)
		const today = frappe.datetime.get_today();
		const monthAgo = frappe.datetime.add_days(today, -30);
		$(wrapper).find('#fin-recon-from').val(monthAgo);
		$(wrapper).find('#fin-recon-to').val(today);

		$(wrapper).find('#btn-fin-recon-run').on('click', function () {
			const $btn = $(this);
			const from = $(wrapper).find('#fin-recon-from').val();
			const to   = $(wrapper).find('#fin-recon-to').val();
			if (!from || !to) { frappe.msgprint('Pick both From and To dates.'); return; }
			$btn.prop('disabled', true).text('Loading…');
			$(wrapper).find('#fin-recon-status').text('Fetching data…');
			$(wrapper).find('#fin-recon-result').hide();
			$(wrapper).find('#btn-fin-recon-excel').hide();
			frappe.call({
				method: API + '.ops_finance_recon_data',
				args: { from_date: from, to_date: to },
				freeze: false,
				callback: function (r) {
					$btn.prop('disabled', false).text('Run');
					const d = r && r.message;
					if (!d || !d.ok) {
						$(wrapper).find('#fin-recon-status').text((d && d.error) || 'Request failed');
						frappe.show_alert({ message: (d && d.error) || 'Finance recon failed', indicator: 'red' }, 5);
						return;
					}
					_fin_data = d;
					_fin_all_rows = d.order_rows || [];
					_fin_page = 0;
					$(wrapper).find('#fin-recon-status').text('Generated at ' + (d.generated_at || ''));
					$(wrapper).find('#btn-fin-recon-excel').show();
					_render_fin_recon(d);
					$(wrapper).find('#fin-recon-result').show();
				},
				error: function () {
					$btn.prop('disabled', false).text('Run');
					$(wrapper).find('#fin-recon-status').text('Request failed');
					frappe.show_alert({ message: 'Request failed', indicator: 'red' }, 5);
				},
			});
		});

		$(wrapper).find('#btn-fin-recon-filter-apply, #fin-recon-filter, #fin-recon-search').on('change click', function (e) {
			if (e.type === 'click' && !$(this).is('#btn-fin-recon-filter-apply')) return;
			if (!_fin_data) return;
			_fin_page = 0;
			_render_fin_order_table();
		});

		$(wrapper).find('#btn-fin-recon-excel').on('click', function () {
			if (!_fin_data) return;
			_fin_export_excel(_fin_data);
		});

		function _render_fin_recon(d) {
			_render_fin_summary(d.summary);
			_render_fin_pivot_table('#fin-recon-channel-table', d.channel_pivot || [], 'Channel');
			_render_fin_pivot_table('#fin-recon-customer-table', d.customer_pivot || [], 'SAP Customer');
			_render_fin_not_posted(d.not_posted || []);
			_fin_all_rows = (d.order_rows || []);
			_fin_page = 0;
			_render_fin_order_table();
		}

		function _render_fin_summary(s) {
			if (!s) return;
			const chip = (label, val, color, subtitle) =>
				`<div style="padding:12px 16px;border-radius:8px;border:1px solid ${color}22;background:${color}10;min-width:130px;text-align:center;">
					<div style="font-size:20px;font-weight:700;color:${color};">${val}</div>
					<div style="font-size:11px;color:#64748b;margin-top:2px;">${esc(label)}</div>
					${subtitle ? `<div style="font-size:10px;color:#94a3b8;margin-top:1px;">${subtitle}</div>` : ''}
				</div>`;
			const fmtAmt = v => '₹' + Number(v||0).toLocaleString('en-IN', {maximumFractionDigits:0});
			const diffColor = v => Math.abs(v||0) < 1 ? '#16a34a' : '#dc2626';
			let html = `<div style="display:flex;gap:10px;flex-wrap:wrap;">
				${chip('Total Orders', fmt(s.total_orders), '#64748b')}
				${chip('Posted to SAP', fmt(s.posted_count), '#16a34a')}
				${chip('Not Posted', fmt(s.not_posted_count), s.not_posted_count ? '#d97706' : '#16a34a')}
				${chip('Mismatches', fmt(s.mismatch_count), s.mismatch_count ? '#dc2626' : '#16a34a', 'diff > ₹1')}
				${chip('UC Taxable Total', fmtAmt(s.uc_taxable_total), '#2563eb')}
				${chip('SAP Taxable Total', fmtAmt(s.sap_taxable_total), '#2563eb')}
				${chip('Taxable Diff', fmtAmt(s.diff_taxable), diffColor(s.diff_taxable), 'SAP - UC')}
				${chip('Tax Diff', fmtAmt(s.diff_tax), diffColor(s.diff_tax), 'SAP - UC')}
			</div>
			<div style="margin-top:10px;padding:8px 12px;background:#f0fdf4;border-radius:6px;border:1px solid #bbf7d0;font-size:12px;font-weight:600;color:#16a34a;">
				Credit Notes — CN Posted: ${fmt(s.cn_posted_count||0)} &nbsp;|&nbsp;
				UC Taxable: ₹${fmtAmt(s.cn_uc_taxable_total)} &nbsp;|&nbsp;
				SAP Taxable: ₹${fmtAmt(s.cn_sap_taxable_total)} &nbsp;|&nbsp;
				<span style="color:${diffColor(s.cn_diff_taxable)};">Taxable Diff: ₹${fmtAmt(s.cn_diff_taxable)}</span>
				&nbsp;|&nbsp; UC Tax: ₹${fmtAmt(s.cn_uc_tax_total)} &nbsp;|&nbsp;
				SAP Tax: ₹${fmtAmt(s.cn_sap_tax_total)} &nbsp;|&nbsp;
				<span style="color:${diffColor(s.cn_diff_tax)};">Tax Diff: ₹${fmtAmt(s.cn_diff_tax)}</span>
			</div>`;
			$(wrapper).find('#fin-recon-summary').html(html);
		}

		function _render_fin_pivot_table(selector, rows, keyLabel) {
			const $t = $(wrapper).find(selector);
			if (!rows.length) { $t.html('<tr><td colspan="14" style="text-align:center;color:#94a3b8;padding:16px;">No data</td></tr>'); return; }
			const fmtAmt = v => Number(v||0).toLocaleString('en-IN', {maximumFractionDigits:0});
			const diffStyle = v => Math.abs(v||0) < 1 ? 'color:#16a34a;' : 'color:#dc2626;font-weight:600;';
			let thead = `<thead>
				<tr>
					<th rowspan="2">${esc(keyLabel)}</th>
					<th rowspan="2" style="text-align:right;">Orders</th>
					<th rowspan="2" style="text-align:right;">Posted</th>
					<th colspan="5" style="text-align:center;background:#eff6ff;border-bottom:2px solid #bfdbfe;">AR Invoice</th>
					<th colspan="7" style="text-align:center;background:#f0fdf4;border-bottom:2px solid #bbf7d0;">Credit Note</th>
					<th rowspan="2" style="text-align:center;">Match?</th>
				</tr>
				<tr>
					<th style="text-align:right;background:#eff6ff;">UC Taxable</th>
					<th style="text-align:right;background:#eff6ff;">SAP Taxable</th>
					<th style="text-align:right;background:#eff6ff;">Diff</th>
					<th style="text-align:right;background:#eff6ff;">UC Tax</th>
					<th style="text-align:right;background:#eff6ff;">SAP Tax</th>
					<th style="text-align:right;background:#f0fdf4;">CN Posted</th>
					<th style="text-align:right;background:#f0fdf4;">UC Taxable</th>
					<th style="text-align:right;background:#f0fdf4;">SAP Taxable</th>
					<th style="text-align:right;background:#f0fdf4;">Diff</th>
					<th style="text-align:right;background:#f0fdf4;">UC Tax</th>
					<th style="text-align:right;background:#f0fdf4;">SAP Tax</th>
					<th style="text-align:right;background:#f0fdf4;">Tax Diff</th>
				</tr>
			</thead>`;
			let tbody = '<tbody>' + rows.map(r => {
				const match = r.mismatches === 0;
				return `<tr>
					<td style="font-weight:600;">${esc(r.key||'—')}</td>
					<td style="text-align:right;">${fmt(r.orders)}</td>
					<td style="text-align:right;">${fmt(r.posted)}</td>
					<td style="text-align:right;background:#eff6ff;">₹${fmtAmt(r.uc_taxable)}</td>
					<td style="text-align:right;background:#eff6ff;">₹${fmtAmt(r.sap_taxable)}</td>
					<td style="text-align:right;background:#eff6ff;${diffStyle(r.diff_taxable)}">₹${fmtAmt(r.diff_taxable)}</td>
					<td style="text-align:right;background:#eff6ff;">₹${fmtAmt(r.uc_tax)}</td>
					<td style="text-align:right;background:#eff6ff;">₹${fmtAmt(r.sap_tax)}</td>
					<td style="text-align:right;background:#f0fdf4;">${fmt(r.cn_posted||0)}</td>
					<td style="text-align:right;background:#f0fdf4;">₹${fmtAmt(r.cn_uc_taxable)}</td>
					<td style="text-align:right;background:#f0fdf4;">₹${fmtAmt(r.cn_sap_taxable)}</td>
					<td style="text-align:right;background:#f0fdf4;${diffStyle(r.cn_diff_taxable)}">₹${fmtAmt(r.cn_diff_taxable)}</td>
					<td style="text-align:right;background:#f0fdf4;">₹${fmtAmt(r.cn_uc_tax)}</td>
					<td style="text-align:right;background:#f0fdf4;">₹${fmtAmt(r.cn_sap_tax)}</td>
					<td style="text-align:right;background:#f0fdf4;${diffStyle(r.cn_diff_tax)}">₹${fmtAmt(r.cn_diff_tax)}</td>
					<td style="text-align:center;">${match ? '<span style="color:#16a34a;font-weight:700;">✓</span>' : `<span style="color:#dc2626;font-weight:700;" title="${r.mismatches} mismatch(es)">✗ ${r.mismatches}</span>`}</td>
				</tr>`;
			}).join('') + '</tbody>';
			$t.html(thead + tbody);
		}

		function _render_fin_not_posted(rows) {
			const $div = $(wrapper).find('#fin-recon-not-posted');
			if (!rows.length) {
				$div.html('<div style="color:#16a34a;font-size:12px;font-weight:600;">✓ All orders in this range are posted to SAP.</div>');
				return;
			}
			const STATUS_COLOR = {
				posted:'#16a34a', ready:'#2563eb', fetched:'#64748b',
				batch_hold:'#d97706', failed:'#dc2626', dead:'#7f1d1d',
				posting:'#7c3aed', verify:'#0284c7', pending:'#94a3b8',
			};
			// Group by status
			const byStatus = {};
			rows.forEach(r => { byStatus[r.status] = (byStatus[r.status]||0) + 1; });
			let html = `<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">
				${Object.entries(byStatus).map(([s,c]) =>
					`<span style="background:#f1f5f9;padding:3px 10px;border-radius:999px;font-size:12px;color:${STATUS_COLOR[s]||'#64748b'};font-weight:600;">${esc(s)}: ${fmt(c)}</span>`
				).join('')}
			</div>`;
			// Show up to 20 rows
			const preview = rows.slice(0, 20);
			html += `<div style="overflow-x:auto;max-height:200px;">
				<table class="table table-bordered" style="font-size:12px;margin:0;">
					<thead><tr><th>Order ID</th><th>Channel</th><th>Date</th><th>Status</th><th>Reason</th></tr></thead>
					<tbody>
						${preview.map(r =>
							`<tr>
								<td><a href="/app/unicommerce-orders/${encodeURIComponent(r.uc_order_id)}" target="_blank">${esc(r.uc_order_id)}</a></td>
								<td>${esc(r.channel||'—')}</td>
								<td>${esc(r.order_date||'')}</td>
								<td style="color:${STATUS_COLOR[r.status]||'#64748b'};font-weight:600;">${esc(r.status||'—')}</td>
								<td style="color:#64748b;">${esc(r.reason||'—')}</td>
							</tr>`
						).join('')}
					</tbody>
				</table>
			</div>`;
			if (rows.length > 20) {
				html += `<div style="font-size:11px;color:#94a3b8;margin-top:4px;">Showing 20 of ${fmt(rows.length)} — download Excel for full list.</div>`;
			}
			$div.html(html);
		}

		function _fin_filtered_rows() {
			const filter = $(wrapper).find('#fin-recon-filter').val() || 'all';
			const search = ($(wrapper).find('#fin-recon-search').val() || '').trim().toLowerCase();
			return _fin_all_rows.filter(r => {
				if (filter === 'mismatch' && r.match !== false) return false;
				if (filter === 'posted' && r.match !== true) return false;
				if (filter === 'not_posted' && r.sap_doc_entry) return false;
				if (search) {
					const hay = ((r.uc_order_id||'') + ' ' + (r.channel||'') + ' ' + (r.sap_doc_num||'')).toLowerCase();
					if (!hay.includes(search)) return false;
				}
				return true;
			});
		}

		function _render_fin_order_table() {
			const rows = _fin_filtered_rows();
			const total = rows.length;
			const start = _fin_page * FIN_PAGE_SIZE;
			const page = rows.slice(start, start + FIN_PAGE_SIZE);
			const fmtAmt = v => Number(v||0).toLocaleString('en-IN', {maximumFractionDigits:0});
			const diffStyle = v => Math.abs(v||0) < 1 ? '' : 'color:#dc2626;font-weight:600;';
			const $t = $(wrapper).find('#fin-recon-order-table');
			let thead = `<thead>
				<tr>
					<th rowspan="2">Order ID</th><th rowspan="2">Channel</th><th rowspan="2">SAP Customer</th>
					<th rowspan="2">Date</th><th rowspan="2">Status</th>
					<th colspan="6" style="text-align:center;background:#eff6ff;color:#1d4ed8;border-bottom:1px solid #bfdbfe;">AR Invoice</th>
					<th rowspan="2" style="text-align:center;background:#eff6ff;color:#1d4ed8;">Match</th>
					<th colspan="7" style="text-align:center;background:#f0fdf4;color:#15803d;border-bottom:1px solid #bbf7d0;">Credit Note</th>
					<th rowspan="2" style="text-align:center;background:#f0fdf4;color:#15803d;">CN Match</th>
				</tr>
				<tr>
					<th style="background:#eff6ff;color:#1d4ed8;">SAP Doc</th>
					<th style="text-align:right;background:#eff6ff;color:#1d4ed8;">UC Taxable</th>
					<th style="text-align:right;background:#eff6ff;color:#1d4ed8;">SAP Taxable</th>
					<th style="text-align:right;background:#eff6ff;color:#1d4ed8;">Price Diff</th>
					<th style="text-align:right;background:#eff6ff;color:#1d4ed8;">UC Tax</th>
					<th style="text-align:right;background:#eff6ff;color:#1d4ed8;">Tax Diff</th>
					<th style="background:#f0fdf4;color:#15803d;">CN SAP Doc</th>
					<th style="text-align:right;background:#f0fdf4;color:#15803d;">UC Taxable</th>
					<th style="text-align:right;background:#f0fdf4;color:#15803d;">SAP Taxable</th>
					<th style="text-align:right;background:#f0fdf4;color:#15803d;">Price Diff</th>
					<th style="text-align:right;background:#f0fdf4;color:#15803d;">UC Tax</th>
					<th style="text-align:right;background:#f0fdf4;color:#15803d;">SAP Tax</th>
					<th style="text-align:right;background:#f0fdf4;color:#15803d;">Tax Diff</th>
				</tr>
			</thead>`;
			const STATUS_COLOR = {
				posted:'#16a34a', ready:'#2563eb', fetched:'#64748b',
				batch_hold:'#d97706', failed:'#dc2626', dead:'#7f1d1d',
				posting:'#7c3aed', verify:'#0284c7', pending:'#94a3b8',
			};
			let tbody = '<tbody>' + page.map(r => {
				const rowBg = r.match === false ? 'background:#fff5f5;' : '';
				const matchIcon = r.match === true ? '<span style="color:#16a34a;">✓</span>'
					: r.match === false ? '<span style="color:#dc2626;font-weight:700;">✗</span>'
					: '<span style="color:#94a3b8;">—</span>';
				const cnMatchIcon = r.cn_match === true ? '<span style="color:#16a34a;">✓</span>'
					: r.cn_match === false ? '<span style="color:#dc2626;font-weight:700;">✗</span>'
					: '<span style="color:#94a3b8;">—</span>';
				const cnDoc = r.cn_sap_doc_num || r.cn_sap_doc_entry || '';
				return `<tr style="${rowBg}">
					<td><a href="/app/unicommerce-orders/${encodeURIComponent(r.uc_order_id)}" target="_blank" style="font-size:11px;">${esc(r.uc_order_id)}</a></td>
					<td>${esc(r.channel||'—')}</td>
					<td style="font-size:11px;color:#475569;">${esc(r.sap_customer||'—')}</td>
					<td style="font-size:11px;">${esc(r.order_date||'')}</td>
					<td style="color:${STATUS_COLOR[r.status]||'#64748b'};font-weight:600;font-size:11px;">${esc(r.status||'—')}</td>
					<td style="font-size:11px;background:#eff6ff;">${esc(r.sap_doc_num||r.sap_doc_entry||'—')}</td>
					<td style="text-align:right;font-size:11px;background:#eff6ff;">₹${fmtAmt(r.uc_taxable)}</td>
					<td style="text-align:right;font-size:11px;background:#eff6ff;">₹${fmtAmt(r.sap_taxable)}</td>
					<td style="text-align:right;font-size:11px;background:#eff6ff;${diffStyle(r.price_diff)}">₹${fmtAmt(r.price_diff)}</td>
					<td style="text-align:right;font-size:11px;background:#eff6ff;">₹${fmtAmt(r.uc_tax)}</td>
					<td style="text-align:right;font-size:11px;background:#eff6ff;${diffStyle(r.tax_diff)}">₹${fmtAmt(r.tax_diff)}</td>
					<td style="text-align:center;background:#eff6ff;">${matchIcon}</td>
					<td style="font-size:11px;background:#f0fdf4;">${cnDoc ? esc(cnDoc) : '—'}</td>
					<td style="text-align:right;font-size:11px;background:#f0fdf4;">${cnDoc ? '₹'+fmtAmt(r.cn_uc_taxable) : '—'}</td>
					<td style="text-align:right;font-size:11px;background:#f0fdf4;">${cnDoc ? '₹'+fmtAmt(r.cn_sap_taxable) : '—'}</td>
					<td style="text-align:right;font-size:11px;background:#f0fdf4;${cnDoc ? diffStyle(r.cn_price_diff) : ''}">${cnDoc ? '₹'+fmtAmt(r.cn_price_diff) : '—'}</td>
					<td style="text-align:right;font-size:11px;background:#f0fdf4;">${cnDoc ? '₹'+fmtAmt(r.cn_uc_tax) : '—'}</td>
					<td style="text-align:right;font-size:11px;background:#f0fdf4;">${cnDoc ? '₹'+fmtAmt(r.cn_sap_tax) : '—'}</td>
					<td style="text-align:right;font-size:11px;background:#f0fdf4;${cnDoc ? diffStyle(r.cn_tax_diff) : ''}">${cnDoc ? '₹'+fmtAmt(r.cn_tax_diff) : '—'}</td>
					<td style="text-align:center;background:#f0fdf4;">${cnDoc ? cnMatchIcon : '<span style="color:#94a3b8;">—</span>'}</td>
				</tr>`;
			}).join('') + '</tbody>';
			$t.html(thead + tbody);

			// Pagination
			const totalPages = Math.ceil(total / FIN_PAGE_SIZE);
			const $pg = $(wrapper).find('#fin-recon-order-pagination');
			$pg.empty();
			if (totalPages > 1) {
				$pg.append(`<span style="font-size:12px;color:#64748b;">Showing ${start+1}–${Math.min(start+FIN_PAGE_SIZE,total)} of ${fmt(total)}</span>`);
				if (_fin_page > 0) {
					$('<button class="btn btn-default btn-xs">← Prev</button>').on('click', function () {
						_fin_page--; _render_fin_order_table();
					}).appendTo($pg);
				}
				if (_fin_page < totalPages - 1) {
					$('<button class="btn btn-default btn-xs">Next →</button>').on('click', function () {
						_fin_page++; _render_fin_order_table();
					}).appendTo($pg);
				}
			} else {
				$pg.append(`<span style="font-size:12px;color:#94a3b8;">${fmt(total)} order(s)</span>`);
			}
		}

		function _fin_export_excel(d) {
			// Build CSV content — simple approach without external library
			const rows = d.order_rows || [];
			const from_d = d.from_date || '';
			const to_d   = d.to_date   || '';

			const csvEsc = v => {
				const s = String(v == null ? '' : v);
				return s.includes(',') || s.includes('"') || s.includes('\n')
					? '"' + s.replace(/"/g, '""') + '"'
					: s;
			};

			// Sheet 1: Summary
			const summaryLines = [
				['Finance Reconciliation Report'],
				['From', from_d, 'To', to_d, 'Generated', d.generated_at||''],
				[],
				['Total Orders', d.summary.total_orders],
				['Posted to SAP', d.summary.posted_count],
				['Not Posted', d.summary.not_posted_count],
				['Mismatches (diff > ₹1)', d.summary.mismatch_count],
				['UC Taxable Total', d.summary.uc_taxable_total],
				['SAP Taxable Total', d.summary.sap_taxable_total],
				['Taxable Diff (SAP-UC)', d.summary.diff_taxable],
				['UC Tax Total', d.summary.uc_tax_total],
				['SAP Tax Total', d.summary.sap_tax_total],
				['Tax Diff (SAP-UC)', d.summary.diff_tax],
				[],
				// Channel pivot header
				['--- Channel Pivot ---'],
				['Channel','Orders','Posted','UC Taxable','SAP Taxable','Taxable Diff','UC Tax','SAP Tax','Tax Diff','Match'],
				...(d.channel_pivot||[]).map(r => [r.key,r.orders,r.posted,r.uc_taxable,r.sap_taxable,r.diff_taxable,r.uc_tax,r.sap_tax,r.diff_tax,r.match?'Yes':'No']),
				[],
				// Customer pivot header
				['--- Customer Pivot ---'],
				['SAP Customer','Orders','Posted','UC Taxable','SAP Taxable','Taxable Diff','UC Tax','SAP Tax','Tax Diff','Match'],
				...(d.customer_pivot||[]).map(r => [r.key,r.orders,r.posted,r.uc_taxable,r.sap_taxable,r.diff_taxable,r.uc_tax,r.sap_tax,r.diff_tax,r.match?'Yes':'No']),
				[],
				// Per-order
				['--- Per Order ---'],
				['Order ID','Channel','SAP Customer','Date','Status','SAP Doc Num','UC Taxable','SAP Taxable','Price Diff','UC Tax','SAP Tax','Tax Diff','Match','CN SAP Doc','CN UC Taxable','CN SAP Taxable','CN Price Diff','CN UC Tax','CN SAP Tax','CN Tax Diff','CN Match','Reason'],
				...rows.map(r => [
					r.uc_order_id, r.channel, r.sap_customer, r.order_date, r.status,
					r.sap_doc_num||r.sap_doc_entry,
					r.uc_taxable, r.sap_taxable, r.price_diff,
					r.uc_tax, r.sap_tax, r.tax_diff,
					r.match === true ? 'Match' : r.match === false ? 'Mismatch' : 'Not Posted',
					r.cn_sap_doc_num||r.cn_sap_doc_entry||'',
					r.cn_uc_taxable||'', r.cn_sap_taxable||'', r.cn_price_diff||'',
					r.cn_uc_tax||'', r.cn_sap_tax||'', r.cn_tax_diff||'',
					r.cn_match === true ? 'Match' : r.cn_match === false ? 'Mismatch' : '',
					r.reason||'',
				]),
			];

			// ── GST Recon pivot (UC by Channel, SAP by Customer) ────────────
			// Build UC channel pivot from order_rows using line-item tax split
			const ucByChannel = {};
			const sapByCustomer = {};
			rows.forEach(r => {
				const ch = r.channel || '—';
				if (!ucByChannel[ch]) ucByChannel[ch] = {orders:0, subtotal:0, discount:0, net_taxable:0, cgst:0, sgst:0, igst:0, total_tax:0};
				ucByChannel[ch].orders++;
				ucByChannel[ch].subtotal     += (r.subtotal    || 0);
				ucByChannel[ch].discount     += (r.uc_discount || 0);
				ucByChannel[ch].net_taxable  += (r.uc_taxable  || 0);
				ucByChannel[ch].cgst         += (r.uc_cgst     || 0);
				ucByChannel[ch].sgst         += (r.uc_sgst     || 0);
				ucByChannel[ch].igst         += (r.uc_igst     || 0);
				ucByChannel[ch].total_tax    += ((r.uc_cgst||0)+(r.uc_sgst||0)+(r.uc_igst||0));

				if (r.sap_doc_entry || r.sap_doc_num) {
					const cust = r.sap_customer || '—';
					if (!sapByCustomer[cust]) sapByCustomer[cust] = {orders:0, sap_taxable:0, cgst:0, sgst:0, igst:0, total_tax:0};
					sapByCustomer[cust].orders++;
					sapByCustomer[cust].sap_taxable += (r.sap_taxable || 0);
					sapByCustomer[cust].cgst        += (r.sap_cgst    || 0);
					sapByCustomer[cust].sgst        += (r.sap_sgst    || 0);
					sapByCustomer[cust].igst        += (r.sap_igst    || 0);
					sapByCustomer[cust].total_tax   += ((r.sap_cgst||0)+(r.sap_sgst||0)+(r.sap_igst||0));
				}
			});
			const rnd = v => Math.round((v||0)*100)/100;
			const gstLines = [
				[],
				['--- GST RECONCILIATION ---'],
				[],
				['== UC Sale Orders by Channel =='],
				['Channel','Orders','Subtotal','Discount','Net Taxable','CGST','SGST','IGST','Total Tax'],
				...Object.entries(ucByChannel).sort((a,b) => b[1].orders - a[1].orders).map(([ch, d]) => [
					ch, d.orders, rnd(d.subtotal), rnd(d.discount), rnd(d.net_taxable),
					rnd(d.cgst), rnd(d.sgst), rnd(d.igst), rnd(d.total_tax)
				]),
				['Grand Total',
					Object.values(ucByChannel).reduce((s,d)=>s+d.orders,0),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.subtotal,0)),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.discount,0)),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.net_taxable,0)),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.cgst,0)),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.sgst,0)),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.igst,0)),
					rnd(Object.values(ucByChannel).reduce((s,d)=>s+d.total_tax,0)),
				],
				[],
				['== SAP AR Invoices by Customer =='],
				['SAP Customer','Orders','SAP Taxable Value','CGST Tax Amount','SGST Tax Amount','IGST Tax Amount','Total Tax'],
				...Object.entries(sapByCustomer).sort((a,b) => b[1].sap_taxable - a[1].sap_taxable).map(([cust, d]) => [
					cust, d.orders, rnd(d.sap_taxable), rnd(d.cgst), rnd(d.sgst), rnd(d.igst), rnd(d.total_tax)
				]),
				['Grand Total',
					Object.values(sapByCustomer).reduce((s,d)=>s+d.orders,0),
					rnd(Object.values(sapByCustomer).reduce((s,d)=>s+d.sap_taxable,0)),
					rnd(Object.values(sapByCustomer).reduce((s,d)=>s+d.cgst,0)),
					rnd(Object.values(sapByCustomer).reduce((s,d)=>s+d.sgst,0)),
					rnd(Object.values(sapByCustomer).reduce((s,d)=>s+d.igst,0)),
					rnd(Object.values(sapByCustomer).reduce((s,d)=>s+d.total_tax,0)),
				],
			];
			summaryLines.push(...gstLines);

			const csvContent = summaryLines.map(line => line.map(csvEsc).join(',')).join('\r\n');
			const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `finance_recon_${from_d}_to_${to_d}.csv`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);
		}
	})();

	// ─── Existing reconciliation ──────────────────────────────────────────
	$(wrapper).find('#btn-recon-refresh').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Running…');
		frappe.call({
			method: API + '.ops_reconciliation_frappe_snapshot',
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				if (r.message) {
					render_reconciliation(r.message);
					load_gst_recon_status();
					load_transfer_summary();
					frappe.show_alert({ message: 'Frappe snapshot reconciliation complete', indicator: 'green' }, 5);
					load_dashboard();
				}
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				frappe.show_alert({ message: 'Reconciliation refresh failed', indicator: 'red' }, 6);
			},
		});
	});
	$(wrapper).find('#btn-recon-refresh-live').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Running…');
		frappe.call({
			method: API + '.ops_reconciliation_live_sap',
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				if (r.message) {
					render_reconciliation(r.message);
					load_gst_recon_status();
					load_transfer_summary();
					frappe.show_alert({ message: 'Live SAP reconciliation complete', indicator: 'green' }, 5);
					load_dashboard();
				}
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				frappe.show_alert({ message: 'Live SAP reconciliation failed', indicator: 'red' }, 6);
			},
		});
	});
	$(wrapper).find('#recon-mode').on('change', function () {
		load_reconciliation();
	});

	function load_transfer_summary() {
		frappe.call({
			method: API + '.ops_transfer_summary',
			freeze: false,
			callback: function (r) {
				const d = r && r.message ? r.message : {};
				const stats = d.stats || {};
				$(wrapper).find('#recon-transfer-summary').html(
					`PO created: <strong>${fmt(stats.po_created || 0)}</strong> · ` +
					`PO approved: <strong>${fmt(stats.po_approved || 0)}</strong> · ` +
					`GRN completed: <strong>${fmt(stats.grn_completed || 0)}</strong> · ` +
					`Posted to UC: <strong>${fmt(stats.posted_to_uc || 0)}</strong> · ` +
					`Pending sync: <strong>${fmt(stats.pending_sync || 0)}</strong> · ` +
					`Failed sync: <strong>${fmt(stats.failed_sync || 0)}</strong>`
				);
			},
		});
	}
	$(wrapper).find('#btn-transfer-summary-refresh').on('click', load_transfer_summary);
	$(wrapper).find('#btn-sync-grn-now').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Running…');
		frappe.call({
			method: API + '.ops_run_worker',
			args: { worker: 'sync_grns' },
			freeze: false,
			callback: function () {
				$btn.prop('disabled', false).text(orig);
				load_transfer_summary();
				load_reconciliation();
				frappe.show_alert({ message: 'GRN sync triggered', indicator: 'green' }, 4);
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				frappe.show_alert({ message: 'GRN sync failed', indicator: 'red' }, 6);
			},
		});
	});
	$(wrapper).find('#btn-sync-inventory-now').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Running…');
		frappe.call({
			method: API + '.ops_run_worker',
			args: { worker: 'sync_inventory' },
			freeze: false,
			callback: function () {
				$btn.prop('disabled', false).text(orig);
				load_transfer_summary();
				load_reconciliation();
				frappe.show_alert({ message: 'Inventory sync triggered', indicator: 'green' }, 4);
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				frappe.show_alert({ message: 'Inventory sync failed', indicator: 'red' }, 6);
			},
		});
	});

	function _series_selection_label(selected, available) {
		if (!available || !available.length) return '—';
		if (!selected || !selected.length || selected.length === available.length) return '(All)';
		if (selected.length === 1) return selected[0];
		if (selected.length <= 3) return selected.join(', ');
		return `Multiple Items (${selected.length})`;
	}

	function _top_pivot_label(rows, labelField, metricField) {
		if (!rows || !rows.length) return '—';
		const ordered = rows.slice().sort((a, b) => num(b[metricField]) - num(a[metricField]));
		return String((ordered[0] && ordered[0][labelField]) || '—');
	}

	function _prepare_sap_pivot_rows(rows, state) {
		rows = rows || [];
		const availableSeries = Array.from(
			new Set(rows.map(r => String(r.SeriesN || '').trim().toUpperCase()).filter(Boolean))
		).sort();
		const savedSelection = Array.isArray(state && state.series_values)
			? state.series_values.map(v => String(v || '').trim().toUpperCase()).filter(v => availableSeries.includes(v))
			: [];
		const activeSeries = savedSelection.length ? savedSelection : availableSeries.slice();
		const filtered = rows.filter(function (row) {
			const series = String(row.SeriesN || '').trim().toUpperCase();
			return !activeSeries.length || activeSeries.includes(series);
		});
		const grouped = {};
		filtered.forEach(function (row) {
			const customerName = String(row['Customer Name'] || '').trim();
			const customerCode = String(row['Customer Code'] || '').trim();
			const label = customerName || customerCode || String(row['Customer Name SeriesN'] || '').trim() || 'Unknown';
			const key = `${customerName || label}||${customerCode}`;
			const cur = grouped[key] || {
				'Customer Name': label,
				'Taxable Value': 0,
				'CGST': 0,
				'SGST': 0,
				'IGST': 0,
				'Total': 0,
			};
			cur['Taxable Value'] += num(row['Taxable Value']);
			cur['CGST'] += num(row.CGST);
			cur['SGST'] += num(row.SGST);
			cur['IGST'] += num(row.IGST);
			cur.Total = cur['Taxable Value'] + cur['CGST'] + cur['SGST'] + cur['IGST'];
			grouped[key] = cur;
		});
		return {
			rows: Object.values(grouped).map(function (row) {
				return {
					'Customer Name': row['Customer Name'],
					'Taxable Value': Math.round(row['Taxable Value'] * 100) / 100,
					'CGST': Math.round(row['CGST'] * 100) / 100,
					'SGST': Math.round(row['SGST'] * 100) / 100,
					'IGST': Math.round(row['IGST'] * 100) / 100,
					'Total': Math.round(row.Total * 100) / 100,
				};
			}),
			availableSeries,
			activeSeries,
			selectionLabel: _series_selection_label(activeSeries, availableSeries),
		};
	}

	function _render_pivot_table($target, rows, columns, money_columns, empty_label, opts) {
		if (!rows || !rows.length) {
			$target.html(`<div style="font-size:12px;color:#6b7280;">${esc(empty_label || 'No rows.')}</div>`);
			return;
		}
		opts = opts || {};
		const moneySet = new Set(money_columns || []);
		const rowLabelField = opts.row_label_field || (columns[0] && columns[0].field) || '';
		const rowLabelHeader = opts.row_label_header || 'Row Labels';
		const valueHeader = opts.value_header || 'Values';
		const reportFilters = opts.report_filters || [];
		const insights = opts.insights || [];
		const numericColumns = columns.filter((c, i) => i > 0 && moneySet.has(c.field));
		const defaultSortBy = numericColumns.find(c => c.field === 'Total')?.field || (numericColumns[0] && numericColumns[0].field) || '';
		const sortBy = numericColumns.some(c => c.field === opts.sort_by) ? opts.sort_by : defaultSortBy;
		const topN = Number(opts.top_n || 0);
		const seriesOptions = opts.series_options || [];
		const seriesSelection = Array.isArray(opts.series_selection) ? opts.series_selection : [];
		const orderedRows = sortBy
			? rows.slice().sort((a, b) => num(b[sortBy]) - num(a[sortBy]))
			: rows.slice();
		const visibleRows = topN > 0 ? orderedRows.slice(0, topN) : orderedRows;
		const head = columns.map((c, i) => `<th style="${i === 0 ? 'text-align:left;' : 'text-align:right;'}">${esc(i === 0 ? rowLabelHeader : (c.label || c.field))}</th>`).join('');
		const body = visibleRows.map(r => `<tr>${columns.map((c, i) => {
			const val = r[c.field];
			if (moneySet.has(c.field)) return `<td style="text-align:right;font-family:monospace;">${money(val)}</td>`;
			const text = val == null ? '' : String(val);
			return `<td style="${i === 0 ? 'font-weight:600;' : 'text-align:right;'}">${esc(text)}</td>`;
		}).join('')}</tr>`).join('');
		const totalsRow = columns.map((c, i) => {
			if (i === 0) return `<td style="font-weight:700;">Grand Total</td>`;
			if (moneySet.has(c.field)) {
				const total = orderedRows.reduce((acc, row) => acc + num(row[c.field]), 0);
				return `<td style="text-align:right;font-family:monospace;font-weight:700;">${money(total)}</td>`;
			}
			return '<td></td>';
		}).join('');
		const pivotId = esc(opts.pivot_key || 'pivot');
		const filterHtml = reportFilters.length ? `
			<div style="padding:10px 12px;border-bottom:1px solid #dbe4f3;background:#f5f9ff;">
				<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:8px;">
					${reportFilters.map(f => `
						<div style="border:1px solid #bfdbfe;border-radius:8px;background:#e0f2fe;padding:8px 10px;">
							<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:#1d4ed8;margin-bottom:3px;">${esc(f.label || '')}</div>
							<div style="font-size:12.5px;font-weight:700;color:#0f172a;">${esc(f.value || '—')}</div>
						</div>
					`).join('')}
				</div>
			</div>
		` : '';
		const insightHtml = insights.length ? `
			<div style="padding:10px 12px;border-bottom:1px solid #dbe4f3;background:#fff;">
				<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;">
					${insights.map(i => `
						<div style="border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;background:${esc(i.bg || '#ffffff')};">
							<div style="font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:#64748b;margin-bottom:3px;">${esc(i.label || '')}</div>
							<div style="font-size:13px;font-weight:700;color:${esc(i.color || '#0f172a')};">${esc(i.value || '—')}</div>
						</div>
					`).join('')}
				</div>
			</div>
		` : '';
		const seriesHtml = seriesOptions.length ? `
			<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
				<span style="color:#64748b;">SeriesN</span>
				<button class="btn btn-default btn-xs" data-pivot-series="${pivotId}" data-series-value="__all__" style="${seriesSelection.length ? '' : 'background:#dbeafe;border-color:#93c5fd;color:#1d4ed8;'}">All</button>
				${seriesOptions.map(series => `
					<button class="btn btn-default btn-xs"
						data-pivot-series="${pivotId}"
						data-series-value="${esc(series)}"
						style="${seriesSelection.includes(series) ? 'background:#dbeafe;border-color:#93c5fd;color:#1d4ed8;' : ''}">
						${esc(series)}
					</button>
				`).join('')}
			</div>
		` : '';
		$target.html(`
			<div style="border:1px solid #dbe4f3;border-radius:8px;background:#fff;overflow:hidden;">
				${filterHtml}
				<div style="padding:8px 10px;border-bottom:1px solid #dbe4f3;background:#edf3ff;color:#1e3a8a;font-size:11px;font-weight:700;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">
					<span>${esc(rowLabelHeader)}: <strong>${esc(rowLabelField || '—')}</strong></span>
					<span>${esc(valueHeader)}: <strong>${esc(columns.slice(1).map(c => c.label || c.field).join(', '))}</strong></span>
				</div>
				${insightHtml}
				<div style="padding:8px 10px;border-bottom:1px solid #dbe4f3;background:#f8fbff;display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:12px;">
					<label style="margin:0;">Sort by
						<select data-pivot-sort="${pivotId}" class="form-control input-sm" style="display:inline-block;width:auto;margin-left:6px;">
							${numericColumns.map(c => `<option value="${esc(c.field)}" ${c.field === sortBy ? 'selected' : ''}>${esc(c.label || c.field)}</option>`).join('')}
						</select>
					</label>
					<label style="margin:0;">Top rows
						<select data-pivot-top-n="${pivotId}" class="form-control input-sm" style="display:inline-block;width:auto;margin-left:6px;">
							${[0, 5, 10, 20, 50, 100].map(n => `<option value="${n}" ${n === topN ? 'selected' : ''}>${n === 0 ? 'All' : String(n)}</option>`).join('')}
						</select>
					</label>
					${seriesHtml}
					<span style="color:#64748b;">Showing <strong>${fmt(visibleRows.length)}</strong> of <strong>${fmt(rows.length)}</strong> rows</span>
				</div>
				<div style="overflow-x:auto;">
				<table class="table table-bordered" style="margin:0;font-size:12px;">
					<thead style="background:#e6eefb;position:sticky;top:0;z-index:1;"><tr>${head}</tr></thead>
					<tbody>${body}<tr style="background:#f8fbff;">${totalsRow}</tr></tbody>
				</table>
				</div>
			</div>
		`);
		$target.find(`[data-pivot-sort="${pivotId}"]`).off('change').on('change', function () {
			if (opts.on_state_change) opts.on_state_change({ sort_by: $(this).val() || defaultSortBy, top_n: topN, series_values: seriesSelection });
		});
		$target.find(`[data-pivot-top-n="${pivotId}"]`).off('change').on('change', function () {
			if (opts.on_state_change) opts.on_state_change({ sort_by: sortBy, top_n: Number($(this).val() || 0), series_values: seriesSelection });
		});
		$target.find(`[data-pivot-series="${pivotId}"]`).off('click').on('click', function () {
			if (!opts.on_state_change) return;
			const value = String($(this).data('seriesValue') || '').trim().toUpperCase();
			if (!value) return;
			if (value === '__all__') {
				opts.on_state_change({ sort_by: sortBy, top_n: topN, series_values: [] });
				return;
			}
			let next = [];
			if (!seriesSelection.length) {
				next = [value];
			} else {
				const selected = new Set(seriesSelection);
				if (selected.has(value)) selected.delete(value);
				else selected.add(value);
				next = Array.from(selected);
			}
			if (!next.length || next.length === seriesOptions.length) next = [];
			opts.on_state_change({ sort_by: sortBy, top_n: topN, series_values: next });
		});
	}

	function gst_recon_readme_html(data) {
		if (!data) {
			return `
				<div class="uc-gst-readme-title">How to read this screen</div>
				<div class="uc-gst-readme-grid">
					<div class="uc-gst-readme-item">
						<div class="uc-gst-readme-kicker">After you run</div>
						<div class="uc-gst-readme-body">You’ll get (1) UC vs SAP totals, (2) a customer/Series roll-up, and (3) a per-order list for anything that still needs action.</div>
					</div>
					<div class="uc-gst-readme-item">
						<div class="uc-gst-readme-kicker">What “good” looks like</div>
						<div class="uc-gst-readme-body">In the roll-up, differences should be <strong>₹0.00</strong> (or within ₹1 if rounding). Use per-order only for exceptions.</div>
					</div>
					<div class="uc-gst-readme-item">
						<div class="uc-gst-readme-kicker">If numbers look off</div>
						<div class="uc-gst-readme-body">Check the <strong>reconciliation date window</strong> and whether you used <em>Posted-to-SAP only</em> (recommended for month-close totals).</div>
					</div>
				</div>
			`;
		}
		const win = data.window || {};
		const winLabel = format_window_label(win.start_date || '', win.end_date || '');
		const mode = (data.compare_mode || 'finance_month');
		const modeLine = mode === 'order_id_trace'
			? 'Order-ID Trace follows specific UC order IDs, even if SAP posted in a different calendar month. Best for support investigations.'
			: 'Finance Month is anchored to the invoice / activity dates you pick — best for month-end vs SAP Finance.';
		const posted = data.posted_only
			? 'Posted-to-SAP only: totals and the roll-up only include rows already in SAP, so the numbers line up with finance’s books.'
			: 'All completed UC rows are in scope: totals can include not-yet-posted work (helpful for pipeline health, not month-close).';
		return `
			<div class="uc-gst-readme-title">How to read this screen</div>
			<div class="uc-gst-readme-grid">
				<div class="uc-gst-readme-item">
					<div class="uc-gst-readme-kicker">Reconciliation window</div>
					<div class="uc-gst-readme-body"><strong>${esc(winLabel || '—')}</strong><div style="margin-top:6px;color:var(--text-muted);font-size:12px;">${esc(modeLine)}</div></div>
				</div>
				<div class="uc-gst-readme-item">
					<div class="uc-gst-readme-kicker">What each block shows</div>
					<div class="uc-gst-readme-body"><strong>1</strong> channel/customer quick totals, <strong>2</strong> a Series/customer check, <strong>3</strong> order-level exceptions with next steps.</div>
				</div>
				<div class="uc-gst-readme-item">
					<div class="uc-gst-readme-kicker">Scope</div>
					<div class="uc-gst-readme-body">${esc(posted)}</div>
				</div>
			</div>
		`;
	}

	function uc_recon_per_order_status_label(status) {
		const s = String(status || '').toLowerCase();
		return ({
			matched: 'Matched',
			amount_mismatch: 'Amounts differ (>₹1)',
			missing_in_sap: 'Not in SAP (this month)',
			missing_in_uc: 'In SAP, not in this UC view',
			not_posted: 'Not posted to SAP yet',
			uc_unmapped: 'Channel not mapped in UC',
			uc_order_outside_export_window: 'UC order date outside this window',
		})[s] || (status || 'Unknown');
	}

	function init_gst_recon_reason_filter() {
		const $sel = $(wrapper).find('#gst-po-filter-reason');
		if (!$sel.length) return;
		const cur = String($sel.val() || '');
		const opts = [
			{ v: 'failed', t: 'Failed in pipeline' },
			{ v: 'batch_hold', t: 'On batch / stock hold' },
			{ v: 'verify', t: 'Needs verification' },
			{ v: 'ready', t: 'Ready to post' },
			{ v: 'pending', t: 'Pending' },
			{ v: 'posting', t: 'Posting in progress' },
			{ v: 'dead', t: 'Permanently blocked' },
			{ v: 'not_ingested', t: 'Not ingested from Unicommerce' },
			{ v: 'posted_outside_window', t: 'Posted, but invoice date is outside the selected month' },
			{ v: 'posted_no_docnum', t: 'Posted, SAP document number not recorded yet' },
			{ v: 'sap_invoice_exists', t: 'SAP invoice already present' },
			{ v: 'uc_order_outside_export_window', t: 'UC order outside export window' },
			{ v: 'no_matching_uc_order', t: 'No matching UC order in this scope' },
			{ v: 'unknown', t: 'Unknown' },
		];
		$sel.empty();
		$sel.append($('<option/>', { value: '', text: 'Any reason' }));
		opts.forEach(function (o) {
			$sel.append($('<option/>', { value: o.v, text: o.t }));
		});
		if (cur) {
			const safe = String(cur).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
			if ($sel.find(`option[value="${safe}"]`).length) $sel.val(cur);
		}
	}

	function init_gst_recon_ui() {
		init_gst_recon_reason_filter();
		$(wrapper).find('#gst-recon-readme').html(gst_recon_readme_html(null));
	}

	function render_gst_recon_status(data) {
		const $meta = $(wrapper).find('#gst-recon-meta');
		const $status = $(wrapper).find('#gst-recon-status');
		const $log = $(wrapper).find('#gst-recon-log');
		const $readme = $(wrapper).find('#gst-recon-readme');
		const $ucPivot = $(wrapper).find('#gst-recon-uc-pivot');
		const $sapPivot = $(wrapper).find('#gst-recon-sap-pivot');
		const $side = $(wrapper).find('#gst-recon-side-by-side');
		const $sidePagination = $(wrapper).find('#gst-recon-side-pagination');
		const $downloadBtn = $(wrapper).find('#btn-gst-recon-download');

		if (!data || data.status === 'not_run') {
			stop_gst_recon_poll();
			$meta.text('No GST reconciliation run recorded yet.');
			$status.html('<div style="font-size:12px;color:#6b7280;">GST reconciliation has not been run yet. Click <strong>Run GST Reconciliation</strong> and pick a date range.</div>');
			$log.html('<div style="background:#0f172a;color:#cbd5e1;border-radius:8px;padding:12px 14px;font-family:monospace;font-size:12px;min-height:90px;">No live run log yet.</div>');
			$readme.html(gst_recon_readme_html(null));
			$ucPivot.html('<div style="font-size:12px;color:#6b7280;">UC pivot will appear after the next run.</div>');
			$sapPivot.html('<div style="font-size:12px;color:#6b7280;">SAP pivot will appear after the next run.</div>');
			$side.html('<div style="font-size:12px;color:#6b7280;">Side-by-side comparison will appear after the next run.</div>');
			$sidePagination.html('');
			$downloadBtn.prop('disabled', true).text('Download Excel');
			return;
		}

		const st = String(data.status || '').toLowerCase();
		const ok = st === 'matched';
		const isBusy = st === 'queued' || st === 'running';
		const indicator = ok ? '#16a34a' : (st === 'error' ? '#dc2626' : '#f59e0b');
		if (isBusy) schedule_gst_recon_poll();
		else stop_gst_recon_poll();

		const win = data.window || {};
		const uc = data.uc || {};
		const sap = data.sap || {};
		const side = data.side_by_side || {};
		const rows = side.rows || [];
		const totals = uc.totals || {};
		const sapTotals = sap.totals || {};
		const windowLabel = format_window_label(win.start_date || '', win.end_date || '');
		const compareMode = (data.compare_mode || 'finance_month');
		const compareModeLabel = compareMode === 'order_id_trace' ? 'Order-ID Trace' : 'Finance Month';
		const compareRowsLabel = data.posted_only
			? `${fmt(uc.completed_rows || 0)} posted rows (of ${fmt(uc.completed_rows_all || uc.completed_rows || 0)} completed)`
			: `${fmt(uc.completed_rows || 0)} completed rows`;
		const sapView = _prepare_sap_pivot_rows(sap.pivot || [], GST_PIVOT_STATE.sap);
		const sapTaxTotal = num(sapTotals.cgst) + num(sapTotals.sgst) + num(sapTotals.igst);
		const progress = data.progress || {};
		const progressLog = data.progress_log || [];
		const fileInfo = data.file || {};
		const canDownload = !isBusy && !!fileInfo.filename;

		$downloadBtn.prop('disabled', !canDownload).text(isBusy ? 'Download After Completion' : 'Download Excel');
		const emailLabel = data.email_to ? ` • email → ${esc(data.email_to)}` : '';
		const postedOnlyLabel = data.posted_only ? ' • <strong style="color:#7c3aed;">Posted-to-SAP only</strong>' : '';
		const modeBadge = ` • <strong style="color:${compareMode === 'order_id_trace' ? '#0f766e' : '#1d4ed8'};">${esc(compareModeLabel)}</strong>`;
		$meta.html(`Last run: ${esc(frappe.datetime.prettyDate(data.generated_at || ''))}${emailLabel}${postedOnlyLabel}${modeBadge}`);

		const configuredSeries = (sap.series_filter || []).join(', ');
		$status.html(`
			<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff;">
				<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
					<span style="width:10px;height:10px;border-radius:50%;background:${indicator};display:inline-block;"></span>
					<strong style="font-size:13px;">${esc(compareModeLabel)} · ${esc((data.status || 'unknown').toUpperCase())}</strong>
					<span style="font-size:12px;color:#6b7280;">Dates: ${esc(windowLabel)}</span>
				</div>
				<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:#334155;">
					<span>Unicommerce rows: <strong>${fmt(uc.master_rows || 0)}</strong> exported • <strong>${esc(compareRowsLabel)}</strong> in the comparison</span>
					<span>SAP rows read: <strong>${fmt(sap.raw_rows || 0)}</strong></span>
					<span>SeriesN filter: <strong>${esc(configuredSeries || 'All / not filtered')}</strong></span>
					${isBusy ? '<span style="color:#92400e;">Updates every 10s while the job is running.</span>' : ''}
					${data.error ? `<span style="color:#dc2626;">Error: ${esc(String(data.error).slice(0, 180))}</span>` : ''}
				</div>
				<div style="margin-top:10px;padding-top:10px;border-top:1px solid #e5e7eb;">
					<div style="font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#64748b;margin-bottom:6px;">Customer / SeriesN roll-up (section 2)</div>
					<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;">
						<div style="border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px;background:#f8fafc;">
							<div style="font-size:11px;color:#64748b;">Rows in roll-up</div>
							<div style="font-size:16px;font-weight:800;color:#0f172a;">${fmt(side.total_rows || 0)}</div>
						</div>
						<div style="border:1px solid #d1fae5;border-radius:8px;padding:8px 10px;background:#ecfdf5;">
							<div style="font-size:11px;color:#065f46;">In sync</div>
							<div style="font-size:16px;font-weight:800;color:#065f46;">${fmt(side.matched || 0)}</div>
						</div>
						<div style="border:1px solid #ffedd5;border-radius:8px;padding:8px 10px;background:#fff7ed;">
							<div style="font-size:11px;color:#9a3412;">Amounts differ (&gt; ₹1)</div>
							<div style="font-size:16px;font-weight:800;color:#9a3412;">${fmt(side.mismatched || 0)}</div>
						</div>
						<div style="border:1px solid #fee2e2;border-radius:8px;padding:8px 10px;background:#fef2f2;">
							<div style="font-size:11px;color:#991b1b;">In UC, not in SAP month</div>
							<div style="font-size:16px;font-weight:800;color:#991b1b;">${fmt(side.missing_in_sap || 0)}</div>
						</div>
						<div style="border:1px solid #ede9fe;border-radius:8px;padding:8px 10px;background:#f5f3ff;">
							<div style="font-size:11px;color:#5b21b6;">In SAP, not in this UC view</div>
							<div style="font-size:16px;font-weight:800;color:#5b21b6;">${fmt(side.missing_in_uc || 0)}</div>
						</div>
						<div style="border:1px solid #bfdbfe;border-radius:8px;padding:8px 10px;background:#eff6ff;">
							<div style="font-size:11px;color:#1d4ed8;">Channel not mapped in UC</div>
							<div style="font-size:16px;font-weight:800;color:#1d4ed8;">${fmt(side.uc_unmapped || 0)}</div>
						</div>
					</div>
					<div style="margin-top:6px;font-size:11.5px;color:#64748b;">These counts explain differences in section 2; section 3 lists the underlying orders to fix or post.</div>
				</div>
				${data.posted_only ? `<div style="margin-top:8px;font-size:12px;color:#7c3aed;"><strong>Posted-to-SAP only</strong> is on: sections 1–2 follow posted invoices. Not-yet-posted orders stay in section 3 with a clear “after posting” outlook.</div>` : ''}
				${compareMode === 'order_id_trace' ? `<div style="margin-top:8px;font-size:12px;color:#0f766e;"><strong>Order-ID trace</strong> widens the SAP look-back so a UC order and its SAP invoice are easier to see together, even if they sit in different calendar months.</div>` : ''}
				${(data.notices || []).length ? `<div style="margin-top:8px;font-size:12px;color:#475569;">${(data.notices || []).map(n => `• ${esc(n)}`).join('<br>')}</div>` : ''}
				<div style="margin-top:8px;font-size:12px;color:#475569;display:flex;gap:14px;flex-wrap:wrap;">
					<span>UC totals — Taxable: <strong>${money(totals.taxable_value)}</strong> • CGST: <strong>${money(totals.cgst)}</strong> • SGST: <strong>${money(totals.sgst)}</strong> • IGST: <strong>${money(totals.igst)}</strong> • Shipping: <strong>${money(totals.shipping)}</strong></span>
					<span>SAP totals — Taxable: <strong>${money(sapTotals.taxable_value)}</strong> • CGST: <strong>${money(sapTotals.cgst)}</strong> • SGST: <strong>${money(sapTotals.sgst)}</strong> • IGST: <strong>${money(sapTotals.igst)}</strong></span>
				</div>
				${progress.label ? `<div style="margin-top:8px;font-size:12px;color:#6b7280;">Step: ${esc(progress.label)}</div>` : ''}
			</div>
		`);

		$log.html(`
			<div style="background:#0f172a;color:#cbd5e1;border-radius:8px;padding:12px 14px;font-family:monospace;font-size:12px;min-height:90px;max-height:220px;overflow-y:auto;white-space:pre-wrap;">
${progressLog.length ? progressLog.map(line => esc(line)).join('\n') : esc('Waiting for run updates...')}
			</div>
		`);
		$readme.html(gst_recon_readme_html(data));

		_render_pivot_table(
			$ucPivot,
			uc.pivot || [],
			[
				{ field: 'Channel', label: 'Channel' },
				{ field: 'Taxable Value', label: 'Taxable Value' },
				{ field: 'CGST', label: 'CGST' },
				{ field: 'SGST', label: 'SGST' },
				{ field: 'IGST', label: 'IGST' },
				{ field: 'Shipping Charges', label: 'Shipping' },
				{ field: 'Total', label: 'Total' },
			],
			['Taxable Value', 'CGST', 'SGST', 'IGST', 'Shipping Charges', 'Total'],
			isBusy ? 'UC pivot will appear after the run completes.' : 'No UC pivot rows.',
			{
				pivot_key: 'uc',
				row_label_field: 'Channel',
				row_label_header: 'Row Labels',
				value_header: 'Values',
				report_filters: [
					{ label: 'Sale Order Status', value: 'COMPLETE / DELIVERED' },
					{ label: 'Date Window', value: windowLabel },
					{ label: 'Rows Considered', value: compareRowsLabel },
				],
				insights: [
					{ label: 'Channels', value: fmt((uc.pivot || []).length), bg: '#f8fafc' },
					{ label: 'Top Channel', value: _top_pivot_label(uc.pivot || [], 'Channel', 'Taxable Value'), bg: '#f8fafc' },
					{ label: 'Tax Mix', value: `${money(num(totals.cgst) + num(totals.sgst))} intra • ${money(totals.igst)} IGST`, bg: '#f8fafc' },
					{ label: 'Shipping', value: money(totals.shipping), bg: '#f8fafc' },
				],
				sort_by: GST_PIVOT_STATE.uc.sort_by,
				top_n: GST_PIVOT_STATE.uc.top_n,
				on_state_change: function (next) {
					GST_PIVOT_STATE.uc = Object.assign({}, GST_PIVOT_STATE.uc, next);
					save_gst_pivot_settings();
					render_gst_recon_status(data);
				},
			}
		);

		_render_pivot_table(
			$sapPivot,
			sapView.rows,
			[
				{ field: 'Customer Name', label: 'Customer Name' },
				{ field: 'Taxable Value', label: 'Taxable Value' },
				{ field: 'CGST', label: 'CGST' },
				{ field: 'SGST', label: 'SGST' },
				{ field: 'IGST', label: 'IGST' },
				{ field: 'Total', label: 'Total' },
			],
			['Taxable Value', 'CGST', 'SGST', 'IGST', 'Total'],
			isBusy ? 'SAP pivot will appear after the run completes.' : 'No SAP pivot rows.',
			{
				pivot_key: 'sap',
				row_label_field: 'Customer Name',
				row_label_header: 'Row Labels',
				value_header: 'Values',
				report_filters: [
					{ label: 'SeriesN', value: sapView.selectionLabel },
					{ label: 'Date Window', value: windowLabel },
					{ label: 'Rows Considered', value: `${fmt(sap.raw_rows || 0)} SAP GST rows` },
				],
				insights: [
					{ label: 'Customers', value: fmt(sapView.rows.length), bg: '#f8fafc' },
					{ label: 'Top Customer', value: _top_pivot_label(sapView.rows, 'Customer Name', 'Taxable Value'), bg: '#f8fafc' },
					{ label: 'Visible Series', value: sapView.availableSeries.length ? `${fmt(sapView.activeSeries.length || sapView.availableSeries.length)} / ${fmt(sapView.availableSeries.length)}` : '0', bg: '#f8fafc' },
					{ label: 'Total Tax', value: money(sapTaxTotal), bg: '#f8fafc' },
				],
				series_options: sapView.availableSeries,
				series_selection: GST_PIVOT_STATE.sap.series_values,
				sort_by: GST_PIVOT_STATE.sap.sort_by,
				top_n: GST_PIVOT_STATE.sap.top_n,
				on_state_change: function (next) {
					GST_PIVOT_STATE.sap = Object.assign({}, GST_PIVOT_STATE.sap, next);
					save_gst_pivot_settings();
					render_gst_recon_status(data);
				},
			}
		);

		const totalRows = Number(side.total_rows || rows.length || 0);
		const totalPages = rows.length ? Math.max(1, Math.ceil(rows.length / RECON_PAGE_SIZE)) : 0;
		if (totalPages && GST_SIDE_BY_SIDE_PAGE > totalPages) GST_SIDE_BY_SIDE_PAGE = totalPages;
		if (!totalPages) GST_SIDE_BY_SIDE_PAGE = 1;
		const slice = rows.length
			? rows.slice((GST_SIDE_BY_SIDE_PAGE - 1) * RECON_PAGE_SIZE, GST_SIDE_BY_SIDE_PAGE * RECON_PAGE_SIZE)
			: [];
		function statusBadge(status) {
			const s = String(status || '').toLowerCase();
			const map = {
				matched: ['#d1fae5', '#065f46', 'Matched'],
				amount_mismatch: ['#fef3c7', '#92400e', 'Amounts differ (>₹1)'],
				missing_in_sap: ['#fee2e2', '#991b1b', 'Not in SAP month'],
				missing_in_uc: ['#ede9fe', '#5b21b6', 'In SAP, not in this UC view'],
				uc_unmapped: ['#dbeafe', '#1e3a8a', 'Channel not mapped'],
				uc_order_outside_export_window: ['#cffafe', '#164e63', 'UC date outside month'],
			};
			const cfg = map[s] || ['#e5e7eb', '#374151', s || 'Unknown'];
			return `<span style="background:${cfg[0]};color:${cfg[1]};padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;">${esc(cfg[2])}</span>`;
		}

		if (!rows.length) {
			$side.html(`<div style="font-size:12px;color:#6b7280;">${
				isBusy
					? 'The customer / SeriesN comparison will fill in as soon as the run produces rows.'
					: 'No roll-up rows for this run (section 3 may still list per-order work).'
			}</div>`);
			$sidePagination.html('');
		} else {
			$side.html(`
				<div style="font-size:12px;color:#6b7280;margin-bottom:8px;">
					Showing <strong>${fmt(slice.length)}</strong> of <strong>${fmt(rows.length)}</strong> roll-up row(s) • ${fmt(totalRows)} total
				</div>
				<div style="overflow-x:auto;">
					<table class="table table-bordered" style="margin:0;font-size:12px;">
						<thead>
							<tr>
								<th>Result</th>
								<th>SAP customer &amp; SeriesN</th>
								<th>Unicommerce channels (facilities)</th>
								<th style="text-align:right;">UC taxable</th>
								<th style="text-align:right;">SAP taxable</th>
								<th style="text-align:right;">Taxable gap (UC − SAP)</th>
								<th style="text-align:right;">UC tax (sum)</th>
								<th style="text-align:right;">SAP tax (sum)</th>
								<th style="text-align:right;">Tax gap (UC − SAP)</th>
								<th style="text-align:right;">UC shipping</th>
							</tr>
						</thead>
						<tbody>
							${slice.map(r => {
								const ucChan = (r.uc_channels || []).join(', ') || '—';
								const ucFac = (r.uc_facilities || []).join(', ');
								const sapLabel = r.sap_label ? `${esc(r.sap_label)}` : `${esc(r.sap_customer_code || '—')} ${esc(r.sap_series || '')}`;
								const uc_tax = Number(r.uc_cgst || 0) + Number(r.uc_sgst || 0) + Number(r.uc_igst || 0);
								const sap_tax = Number(r.sap_cgst || 0) + Number(r.sap_sgst || 0) + Number(r.sap_igst || 0);
								const taxableDiff = Number(r.taxable_diff || 0);
								const taxDiff = Number(r.tax_diff || 0);
								const taxableColor = Math.abs(taxableDiff) > 1.0 ? '#dc2626' : '#16a34a';
								const taxColor = Math.abs(taxDiff) > 1.0 ? '#dc2626' : '#16a34a';
								return `<tr>
									<td>${statusBadge(r.status)}</td>
									<td>${sapLabel}</td>
									<td>${esc(ucChan)}${ucFac ? `<div style="color:#94a3b8;font-size:11px;">${esc(ucFac)}</div>` : ''}</td>
									<td style="text-align:right;font-family:monospace;">${money(r.uc_taxable_value)}</td>
									<td style="text-align:right;font-family:monospace;">${money(r.sap_taxable_value)}</td>
									<td style="text-align:right;font-family:monospace;color:${taxableColor};font-weight:700;">${money(taxableDiff)}</td>
									<td style="text-align:right;font-family:monospace;">${money(uc_tax)}</td>
									<td style="text-align:right;font-family:monospace;">${money(sap_tax)}</td>
									<td style="text-align:right;font-family:monospace;color:${taxColor};font-weight:700;">${money(taxDiff)}</td>
									<td style="text-align:right;font-family:monospace;">${money(r.uc_shipping)}</td>
								</tr>`;
							}).join('')}
						</tbody>
					</table>
				</div>
			`);
			$sidePagination.html(rows.length ? `
				${page_size_selector('gst-recon-page-size', RECON_PAGE_SIZE)}
				<button class="btn btn-default btn-xs" ${GST_SIDE_BY_SIDE_PAGE <= 1 ? 'disabled' : ''} data-gst-side-prev="1">Prev</button>
				<span style="font-size:12px;color:#64748b;">Page ${GST_SIDE_BY_SIDE_PAGE} / ${totalPages} • ${fmt(totalRows)} rows</span>
				<button class="btn btn-default btn-xs" ${GST_SIDE_BY_SIDE_PAGE >= totalPages ? 'disabled' : ''} data-gst-side-next="1">Next</button>
			` : '');
		}
		$(wrapper).find('#gst-recon-page-size').off('change').on('change', function () {
			RECON_PAGE_SIZE = Number($(this).val() || 20);
			GST_SIDE_BY_SIDE_PAGE = 1;
			try { window.localStorage.setItem(RECON_PAGE_SIZE_KEY, String(RECON_PAGE_SIZE)); } catch (e) {}
			render_gst_recon_status(data);
		});
		$(wrapper).find('[data-gst-side-prev="1"]').off('click').on('click', function () {
			if (GST_SIDE_BY_SIDE_PAGE > 1) {
				GST_SIDE_BY_SIDE_PAGE -= 1;
				render_gst_recon_status(data);
			}
		});
		$(wrapper).find('[data-gst-side-next="1"]').off('click').on('click', function () {
			if (GST_SIDE_BY_SIDE_PAGE < totalPages) {
				GST_SIDE_BY_SIDE_PAGE += 1;
				render_gst_recon_status(data);
			}
		});

		render_gst_per_order_summary(data.per_order || {}, data.window || {});
		load_gst_per_order({ reset_page: false });
	}

	// ─── Per-order diagnostics (one UC order compared to SAP posting) ─────────────

	let PER_ORDER_PAGE_SIZE = 50;
	let PER_ORDER_PAGE = 1;

	function render_gst_per_order_summary(po, win) {
		win = win || {};
		const $tiles = $(wrapper).find('#gst-recon-per-order-tiles');
		const $reasons = $(wrapper).find('#gst-recon-per-order-reasons');
		const summary = po.summary || {};
		if (!Object.keys(summary).length) {
			$tiles.html('<div style="font-size:12px;color:#6b7280;">Per-order diagnostics will appear after the next run.</div>');
			$reasons.html('');
			return;
		}
		// clickStatus: filters the per-order table; 'matched' opens UC Orders list since matched rows aren't cached
		const tile = (label, value, color, sub, clickStatus) => {
			const clickable = !!clickStatus;
			const cursor = clickable ? 'cursor:pointer;' : '';
			const hoverAttr = clickable ? `data-tile-status="${esc(clickStatus)}"` : '';
			return `
				<div ${hoverAttr} style="min-width:140px;flex:1;background:#fff;border:1px solid #e5e7eb;border-left:4px solid ${color};border-radius:6px;padding:10px 12px;${cursor}transition:box-shadow 0.15s,border-color 0.15s;" ${clickable ? `class="uc-po-tile-clickable"` : ''}>
					<div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.3px;">${esc(label)}</div>
					<div style="font-size:20px;font-weight:700;color:#0f172a;margin-top:2px;">${fmt(value || 0)}</div>
					${sub ? `<div style="font-size:11px;color:#64748b;margin-top:2px;">${esc(sub)}</div>` : ''}
					${clickable ? `<div style="font-size:10px;color:${color};margin-top:4px;opacity:0.7;">Click to view details ↓</div>` : ''}
				</div>
			`;
		};
		$tiles.html(`
			${tile('Matched', summary.matched, '#16a34a', 'UC ≈ SAP (±₹1)', 'matched')}
			${tile('Amount Mismatch', summary.amount_mismatch, '#f59e0b', '|UC − SAP| > ₹1', 'amount_mismatch')}
			${tile('Not found in SAP month', summary.missing_in_sap, '#dc2626', 'Likely posted with DocDate outside selected month', 'missing_in_sap')}
			${(summary.not_posted || 0) > 0 ? tile('Not posted to SAP yet', summary.not_posted, '#2563eb', 'Excluded from posted-only compare', 'not_posted') : ''}
			${(summary.not_posted_blocked || 0) > 0 ? tile('Posting Blocked', summary.not_posted_blocked, '#b91c1c', 'Needs posting fix before compare', 'not_posted') : ''}
			${tile('SAP-only rows', summary.missing_in_uc, '#8b5cf6', 'Invoice exists in SAP but UC row is outside selected scope', 'missing_in_uc')}
			${(summary.uc_order_outside_export_window || 0) > 0 ? tile('Cross-period orders', summary.uc_order_outside_export_window, '#0891b2', 'UC order date and selected month are different', 'uc_order_outside_export_window') : ''}
			${tile('UC Total ₹', summary.uc_total, '#2563eb')}
			${tile('SAP Total ₹', summary.sap_total, '#0ea5e9')}
			${tile('Δ UC − SAP', summary.total_diff, Math.abs(Number(summary.total_diff || 0)) > 1 ? '#dc2626' : '#16a34a')}
		`);

		// Wire click handlers for the 4 status tiles
		$tiles.find('.uc-po-tile-clickable').off('click').on('click', function () {
			const tileStatus = $(this).attr('data-tile-status');
			if (!tileStatus) return;

			if (tileStatus === 'matched') {
				// Matched rows are not cached — navigate to Unicommerce Orders list filtered to posted orders in the window
				const startDate = win.start_date || (po.summary && po.summary._start_date) || '';
				const endDate   = win.end_date   || (po.summary && po.summary._end_date)   || '';
				const routeFilters = { pipeline_status: 'posted' };
				if (startDate && endDate) {
					routeFilters['order_date'] = ['between', [startDate, endDate]];
				}
				frappe.route_options = routeFilters;
				frappe.set_route('List', 'Unicommerce Orders');
				return;
			}

			// For all other statuses: filter the per-order table and scroll to it
			$(wrapper).find('#gst-po-filter-status').val(tileStatus);
			$(wrapper).find('#gst-po-filter-reason').val('');
			$(wrapper).find('#gst-po-filter-search').val('');
			PER_ORDER_PAGE = 1;
			load_gst_per_order({ reset_page: true });
			const $section = $(wrapper).find('#gst-recon-per-order-tiles');
			if ($section.length) {
				$section[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
			}
		});

		// Hover highlight for clickable tiles
		$tiles.find('.uc-po-tile-clickable')
			.on('mouseenter', function () {
				$(this).css({ 'box-shadow': '0 2px 10px rgba(0,0,0,0.10)', 'border-color': '#d1d5db' });
			})
			.on('mouseleave', function () {
				$(this).css({ 'box-shadow': '', 'border-color': '#e5e7eb' });
			});

		const reasons = summary.missing_in_sap_by_reason || {};
		const reasonEntries = Object.keys(reasons).sort((a, b) => (reasons[b] || 0) - (reasons[a] || 0));
		const notPostedReasons = summary.not_posted_by_reason || {};
		const notPostedEntries = Object.keys(notPostedReasons).sort((a, b) => (notPostedReasons[b] || 0) - (notPostedReasons[a] || 0));
		if (!reasonEntries.length && !notPostedEntries.length) {
			$reasons.html('<div style="font-size:12px;color:#6b7280;">No category breakdown is required for this run.</div>');
			return;
		}
			const reasonLegend = {
				failed: ['#fee2e2', '#991b1b', 'SAP POST failed — check last_error'],
				batch_hold: ['#fef3c7', '#92400e', 'Waiting for batch cooldown'],
				verify: ['#e0e7ff', '#3730a3', 'Ack missing — pending verification'],
				ready: ['#dbeafe', '#1e3a8a', 'Queued for posting'],
				pending: ['#e0f2fe', '#075985', 'Pending before posting'],
				posting: ['#dbeafe', '#1e40af', 'Currently posting'],
				dead: ['#fce7f3', '#9f1239', 'Max retries exhausted'],
				not_ingested: ['#f3e8ff', '#6d28d9', 'Order never reached Frappe'],
				posted_outside_window: ['#e0f2fe', '#0369a1', 'Posted, but SAP posting month differs from selected month'],
				posted_no_docnum: ['#fee2e2', '#991b1b', 'Marked posted but no DocNum'],
				sap_invoice_exists: ['#ede9fe', '#6d28d9', 'SAP invoice already exists, but Frappe still shows the order as not posted'],
				fetched: ['#f1f5f9', '#334155', 'Fetched but not promoted'],
				uc_order_outside_export_window: ['#fef9c3', '#854d0e', 'Order exists in Frappe — UC creation date is outside this window (cross-period invoice)'],
				no_matching_uc_order: ['#fce7f3', '#9f1239', 'SAP invoice references a UC order ID that has no Frappe record at all'],
				sap_posted_for_uc_order_outside_window: ['#fef9c3', '#854d0e', 'Order creation date outside export window (legacy label)'],
				unknown: ['#e5e7eb', '#374151', 'Unrecognised pipeline_status'],
			};
		$reasons.html(`
			${reasonEntries.length ? `<div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#374151;">Not found in SAP month - reason breakdown</div>
			<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
				${reasonEntries.map(k => {
					const legend = reasonLegend[k] || ['#e5e7eb', '#374151', k];
					return `<button class="btn btn-xs" data-po-reason="${esc(k)}" data-po-status="missing_in_sap" style="background:${legend[0]};color:${legend[1]};border:1px solid ${legend[1]}22;font-weight:600;">
						${esc(k)} <span style="font-weight:400;opacity:0.75;">· ${fmt(reasons[k])}</span>
					</button>`;
				}).join('')}
			</div>` : ''}
				${notPostedEntries.length ? `<div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#374151;">Not posted to SAP yet - cause breakdown</div>
				<div style="display:flex;gap:8px;flex-wrap:wrap;">
					${notPostedEntries.map(k => {
						const legend = reasonLegend[k] || ['#e5e7eb', '#374151', k];
						return `<button class="btn btn-xs" data-po-reason="${esc(k)}" data-po-status="not_posted" style="background:${legend[0]};color:${legend[1]};border:1px solid ${legend[1]}22;font-weight:600;">
							${esc(k)} <span style="font-weight:400;opacity:0.75;">· ${fmt(notPostedReasons[k])}</span>
						</button>`;
					}).join('')}
				</div>` : ''}
			`);
		$(wrapper).find('[data-po-reason]').off('click').on('click', function () {
			const code = $(this).attr('data-po-reason') || '';
			const status = $(this).attr('data-po-status') || 'missing_in_sap';
			$(wrapper).find('#gst-po-filter-status').val(status);
			$(wrapper).find('#gst-po-filter-reason').val(code);
			PER_ORDER_PAGE = 1;
			load_gst_per_order({ reset_page: true });
		});
	}

	function _po_row_html(r) {
		// For missing_in_uc rows that have a uc_order_name, the order exists in
		// Frappe — its UC creation date is just outside the export window.
		// Show the link so the user can verify it directly.
		const ucOrderDesk = r.uc_order_name
			? `<a href="/app/unicommerce-orders/${encodeURIComponent(r.uc_order_name)}" target="_blank">${esc(r.order_id)}</a>`
			: esc(r.order_id || '');
			const reasonText = String(r.reason_label || r.reason_code || '').trim();
			const reasonChip = reasonText
				? `<span style="background:#f8fafc;color:#475569;border:1px solid #e2e8f0;padding:1px 6px;border-radius:999px;font-size:11px;font-weight:600;">${esc(reasonText)}</span>`
				: '';
			const pipelineChip = r.pipeline_status
				? `<div style="color:#64748b;font-size:11px;margin-top:2px;">pipeline: <strong>${esc(r.pipeline_status)}</strong>${r.attempt_count ? ` · attempts: ${esc(String(r.attempt_count))}` : ''}</div>`
				: '';
			const errorBlock = r.last_error
				? `<div style="color:#b91c1c;font-size:11px;margin-top:2px;white-space:pre-wrap;max-width:380px;">${esc(String(r.last_error).slice(0, 260))}</div>`
				: '';
			const hasComparison = r.comparison_available !== false;
			const showSapValues = hasComparison || !!r.sap_docnum || (r.sap_total !== null && r.sap_total !== undefined);
			const showDiff = hasComparison || (r.total_diff !== null && r.total_diff !== undefined);
			const totalDiff = showDiff ? Number(r.total_diff || 0) : 0;
			const diffColor = Math.abs(totalDiff) > 1 ? '#dc2626' : '#16a34a';
			const statusMap = {
				matched: ['#d1fae5', '#065f46'],
				amount_mismatch: ['#fef3c7', '#92400e'],
				missing_in_sap: ['#fee2e2', '#991b1b'],
				not_posted: ['#dbeafe', '#1d4ed8'],
				missing_in_uc: ['#ede9fe', '#5b21b6'],
				uc_order_outside_export_window: ['#cffafe', '#164e63'],
			};
			const sc = statusMap[r.status] || ['#e5e7eb', '#374151'];
			const outlookToneMap = {
				good: ['#d1fae5', '#065f46'],
				warn: ['#fef3c7', '#92400e'],
				bad: ['#fee2e2', '#991b1b'],
				info: ['#dbeafe', '#1d4ed8'],
			};
			const oc = outlookToneMap[r.post_then_match_tone] || outlookToneMap.info;
			const outlookChip = r.post_then_match_label
				? `<span style="display:inline-flex;align-items:center;padding:3px 8px;border-radius:999px;background:${oc[0]};color:${oc[1]};font-size:11px;font-weight:700;">${esc(r.post_then_match_label)}</span>`
				: '<span style="color:#94a3b8;font-size:11px;">—</span>';
			return `<tr>
				<td>
					<span style="background:${sc[0]};color:${sc[1]};padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;">${esc(uc_recon_per_order_status_label(r.status))}</span>
					${reasonChip ? `<div style="margin-top:4px;">${reasonChip}</div>` : ''}
				</td>
				<td>
					<div style="font-family:monospace;font-size:12px;">${ucOrderDesk}</div>
					<div style="color:#64748b;font-size:11px;margin-top:2px;">${esc(r.channel || '')}${r.facility ? ` · ${esc(r.facility)}` : ''}</div>
					${r.uc_order_date ? `<div style="color:#94a3b8;font-size:11px;">ordered ${esc(String(r.uc_order_date).slice(0, 10))}</div>` : ''}
					${pipelineChip}
					${errorBlock}
				</td>
				<td style="text-align:right;font-family:monospace;">${money(r.uc_total)}</td>
				<td>
					${r.sap_docnum ? `<div style="font-family:monospace;font-size:12px;">${esc(r.sap_docnum)}</div>` : '<div style="color:#94a3b8;font-size:11px;">—</div>'}
					${r.sap_series ? `<div style="color:#64748b;font-size:11px;margin-top:2px;">${esc(r.sap_series)}${r.sap_customer_name ? ` · ${esc(r.sap_customer_name)}` : ''}</div>` : ''}
					${r.sap_doc_date ? `<div style="color:#94a3b8;font-size:11px;">posted ${esc(String(r.sap_doc_date).slice(0, 10))}</div>` : ''}
				</td>
				<td style="text-align:right;font-family:monospace;">${showSapValues ? money(r.sap_total) : '<span style="color:#94a3b8;">—</span>'}</td>
				<td>${outlookChip}</td>
				<td style="text-align:right;font-family:monospace;color:${diffColor};font-weight:700;">${showDiff ? money(totalDiff) : '<span style="color:#94a3b8;">—</span>'}</td>
			</tr>`;
		}

	function load_gst_per_order(opts) {
		opts = opts || {};
		if (opts.reset_page) PER_ORDER_PAGE = 1;
		const status = $(wrapper).find('#gst-po-filter-status').val() || '';
		const reason_code = $(wrapper).find('#gst-po-filter-reason').val() || '';
		const search = ($(wrapper).find('#gst-po-filter-search').val() || '').trim();
		const start = (PER_ORDER_PAGE - 1) * PER_ORDER_PAGE_SIZE;

		const $table = $(wrapper).find('#gst-recon-per-order');
		const $pag = $(wrapper).find('#gst-recon-per-order-pagination');
		const $count = $(wrapper).find('#gst-po-count');
		$table.html('<div style="font-size:12px;color:#6b7280;">Loading per-order rows…</div>');
		$pag.html('');

		frappe.call({
			method: API + '.gst_reconciliation_per_order',
			args: { status, reason_code, search, start, page_size: PER_ORDER_PAGE_SIZE },
			freeze: false,
			callback: function (r) {
				const data = (r && r.message) || {};
				const rows = data.rows || [];
				const total = Number(data.filtered_total || 0);
				const actionable = Number(data.actionable_count || 0);
				const storedTotal = Number(data.total_rows || 0);
				const notPosted = Number((data.summary && data.summary.not_posted) || 0);
				const compareIssues = actionable > 0 ? `${fmt(actionable)} compare issues` : '0 compare issues';
				const notPostedLabel = notPosted > 0 ? ` · ${fmt(notPosted)} not posted yet` : '';
				$count.text(`${compareIssues}${notPostedLabel} · filter shows ${fmt(total)} of ${fmt(storedTotal)} cached rows`);
				if (!rows.length) {
					$table.html(`<div style="font-size:12px;color:#6b7280;">
						${total === 0 && actionable === 0 && storedTotal > 0
							? (notPosted > 0
								? 'There are no comparison mismatches in the selected scope. Only not-posted orders remain for review.'
								: 'Every UC order in this window matches a SAP invoice within ±₹1. Nothing to diagnose.')
							: 'No rows match the current filter.'}
					</div>`);
					return;
				}
				$table.html(`
					<div style="overflow-x:auto;">
						<table class="table table-bordered" style="margin:0;font-size:12px;">
							<thead>
								<tr>
									<th style="min-width:140px;">What we found</th>
									<th>UC Order</th>
									<th style="text-align:right;">UC Total</th>
									<th>SAP DocNum</th>
									<th style="text-align:right;">SAP Total</th>
									<th>Can this match after posting?</th>
									<th style="text-align:right;">Difference (UC - SAP)</th>
								</tr>
							</thead>
							<tbody>${rows.map(_po_row_html).join('')}</tbody>
						</table>
					</div>
				`);
				const totalPages = Math.max(1, Math.ceil(total / PER_ORDER_PAGE_SIZE));
				if (PER_ORDER_PAGE > totalPages) PER_ORDER_PAGE = totalPages;
				$pag.html(`
					<button class="btn btn-default btn-xs" ${PER_ORDER_PAGE <= 1 ? 'disabled' : ''} data-po-prev="1">Prev</button>
					<span style="font-size:12px;color:#64748b;">Page ${PER_ORDER_PAGE} / ${totalPages} · ${fmt(total)} rows</span>
					<button class="btn btn-default btn-xs" ${PER_ORDER_PAGE >= totalPages ? 'disabled' : ''} data-po-next="1">Next</button>
				`);
				$(wrapper).find('[data-po-prev="1"]').off('click').on('click', function () {
					if (PER_ORDER_PAGE > 1) { PER_ORDER_PAGE -= 1; load_gst_per_order({ reset_page: false }); }
				});
				$(wrapper).find('[data-po-next="1"]').off('click').on('click', function () {
					if (PER_ORDER_PAGE < totalPages) { PER_ORDER_PAGE += 1; load_gst_per_order({ reset_page: false }); }
				});
			},
			error: function () {
				$table.html('<div style="font-size:12px;color:#dc2626;">Failed to load per-order diagnostics.</div>');
			},
		});
	}

	$(wrapper).find('#gst-po-filter-apply').on('click', function () {
		load_gst_per_order({ reset_page: true });
	});
	$(wrapper).find('#gst-po-filter-reset').on('click', function () {
		$(wrapper).find('#gst-po-filter-status').val('');
		$(wrapper).find('#gst-po-filter-reason').val('');
		$(wrapper).find('#gst-po-filter-search').val('');
		load_gst_per_order({ reset_page: true });
	});
	$(wrapper).find('#gst-po-filter-search').on('keydown', function (e) {
		if (e.key === 'Enter') load_gst_per_order({ reset_page: true });
	});

	function load_gst_recon_status() {
		frappe.call({
			method: API + '.gst_reconciliation_status',
			freeze: false,
			callback: function (r) {
				render_gst_recon_status(r.message || {});
			},
			error: function () {
				$(wrapper).find('#gst-recon-meta').text('Failed to load GST reconciliation status');
			},
		});
	}

	$(wrapper).find('#btn-gst-recon-run').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		prompt_date_range(
			{
				title: 'GST Reconciliation — pick start + end date',
				intro: 'The reconciliation will pull a fresh UC export for every facility (typically 5–25 minutes), run the SAP GSTR1 HANA query, and produce UC + SAP pivots and a side-by-side comparison. Bounds are inclusive (YYYY-MM-DD).',
				primary_action_label: 'Queue GST Reconciliation',
				ask_email: true,
				ask_posted_only: true,
			},
			function (range) {
				$btn.prop('disabled', true).text('Queueing…');
				// Reset all per-tab paginators so the next snapshot renders
				// page 1 consistently regardless of where the user was.
				GST_SIDE_BY_SIDE_PAGE = 1;
				PER_ORDER_PAGE = 1;
				frappe.call({
					method: API + '.gst_reconciliation_run_async',
					args: {
						start_date: range.start_date,
						end_date: range.end_date,
						email_to: range.email_to || null,
						posted_only: range.posted_only ? 1 : 0,
						compare_mode: range.compare_mode || 'finance_month',
					},
					callback: function (r) {
						$btn.prop('disabled', false).text(orig);
						render_gst_recon_status(r.message || {});
						const st = (r.message && r.message.status) || 'unknown';
						let msg = st === 'queued' ? 'GST reconciliation queued' : `GST reconciliation completed (${st})`;
						if (range.email_to) msg += ` • will email ${range.email_to} on success`;
						frappe.show_alert(
							{ message: msg, indicator: st === 'matched' ? 'green' : 'orange' },
							9
						);
					},
					error: function (err) {
						$btn.prop('disabled', false).text(orig);
						const reason = (err && err.message) ? String(err.message) : 'GST reconciliation request failed';
						frappe.show_alert({ message: reason, indicator: 'red' }, 9);
					},
				});
			}
		);
	});

	$(wrapper).find('#btn-gst-recon-download').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Preparing…');
		frappe.call({
			method: API + '.gst_reconciliation_download_last_run',
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				const msg = r.message || {};
				if (msg.file_url) {
					window.open(msg.file_url, '_blank');
					frappe.show_alert({ message: 'Excel ready', indicator: 'green' }, 7);
				} else {
					frappe.show_alert({ message: 'No Excel file was generated', indicator: 'orange' }, 7);
				}
			},
			error: function (err) {
				$btn.prop('disabled', false).text(orig);
				const msg = (err && err.message) ? String(err.message) : 'Workbook will be available after the reconciliation completes';
				frappe.show_alert({ message: msg, indicator: 'orange' }, 7);
			},
		});
	});

	function render_reconciliation(data) {
		const ok_html = '<div style="background:#d4edda;border:1px solid #c3e6cb;border-radius:6px;padding:12px 16px;color:#155724;font-size:12px;font-weight:600;">✓ None found.</div>';
		function render_recon_pagination(target, page, total_rows, on_prev, on_next) {
			const total_pages = Math.max(1, Math.ceil(total_rows / RECON_PAGE_SIZE));
			$(target).html(total_rows ? `
				${page_size_selector('recon-page-size', RECON_PAGE_SIZE)}
				<button class="btn btn-default btn-xs" ${page <= 1 ? 'disabled' : ''} data-recon-prev="${target}">Prev</button>
				<span style="font-size:12px;color:#64748b;">Page ${page} / ${total_pages} • ${fmt(total_rows)} rows</span>
				<button class="btn btn-default btn-xs" ${page >= total_pages ? 'disabled' : ''} data-recon-next="${target}">Next</button>
			` : '');
			$(wrapper).find('#recon-page-size').off('change').on('change', function () {
				RECON_PAGE_SIZE = Number($(this).val() || 20);
				RECON_GAPS_PAGE = 1;
				RECON_GRN_PAGE = 1;
				RECON_INV_PAGE = 1;
				try { window.localStorage.setItem(RECON_PAGE_SIZE_KEY, String(RECON_PAGE_SIZE)); } catch (e) {}
				render_reconciliation(data);
			});
			$(wrapper).find(`[data-recon-prev="${target}"]`).off('click').on('click', on_prev);
			$(wrapper).find(`[data-recon-next="${target}"]`).off('click').on('click', on_next);
		}

		const gaps = data.invoice_gaps || [];
		const $gaps = $(wrapper).find('#recon-invoice-gaps');
		if (!gaps.length) { $gaps.html(ok_html); }
		else {
			const gaps_pages = Math.max(1, Math.ceil(gaps.length / RECON_PAGE_SIZE));
			if (RECON_GAPS_PAGE > gaps_pages) RECON_GAPS_PAGE = gaps_pages;
			const gaps_slice = gaps.slice((RECON_GAPS_PAGE - 1) * RECON_PAGE_SIZE, RECON_GAPS_PAGE * RECON_PAGE_SIZE);
			$gaps.html(`<div style="font-size:12px;color:#856404;margin-bottom:8px;font-weight:600;">${gaps.length} gap(s) found.</div>
				<div style="overflow-x:auto;"><table class="table table-bordered" style="margin:0;font-size:12px;">
				<thead><tr><th>Order ID</th><th>Source</th><th>Tax Expected</th><th>Tax Actual</th><th>Tax Diff</th><th>Price Diff</th><th>Modified</th></tr></thead>
				<tbody>${gaps_slice.map(g => `<tr>
					<td><a href="/app/${doctype_route(g.record_doctype)}/${encodeURIComponent(g.record_name)}" target="_blank" style="color:#0d6efd;">${esc(g.uc_order_id||g.record_name)}</a></td>
					<td>${esc((g.source || 'staging') + ' / ' + (g.document_type || 'invoice'))}</td>
					<td>${money(g.tax_expected)}</td><td>${money(g.tax_actual)}</td>
					<td style="color:#dc3545;font-weight:600;">${money(g.tax_diff)}</td>
					<td style="color:#fd7e14;font-weight:600;">${money(g.unit_price_diff)}</td>
					<td style="color:#6c757d;">${esc(frappe.datetime.prettyDate(g.modified))}</td>
				</tr>`).join('')}</tbody></table></div>`);
		}
		render_recon_pagination('#recon-gaps-pagination', RECON_GAPS_PAGE, gaps.length,
			function () { if (RECON_GAPS_PAGE > 1) { RECON_GAPS_PAGE -= 1; render_reconciliation(data); } },
			function () { if (RECON_GAPS_PAGE * RECON_PAGE_SIZE < gaps.length) { RECON_GAPS_PAGE += 1; render_reconciliation(data); } }
		);

		const grn = data.grn_drift || [];
		const $grn = $(wrapper).find('#recon-grn-drift');
		if (!grn.length) { $grn.html(ok_html); }
		else {
			const grn_pages = Math.max(1, Math.ceil(grn.length / RECON_PAGE_SIZE));
			if (RECON_GRN_PAGE > grn_pages) RECON_GRN_PAGE = grn_pages;
			const grn_slice = grn.slice((RECON_GRN_PAGE - 1) * RECON_PAGE_SIZE, RECON_GRN_PAGE * RECON_PAGE_SIZE);
			$grn.html(`<div style="font-size:12px;color:#856404;margin-bottom:8px;font-weight:600;">${grn.length} APPROVED PO(s) stale.</div>
				<div style="overflow-x:auto;"><table class="table table-bordered" style="margin:0;font-size:12px;">
				<thead><tr><th>Transfer</th><th>Doc Num</th><th>PO ID</th><th>Modified</th></tr></thead>
				<tbody>${grn_slice.map(g => `<tr>
					<td><a href="/app/sap-inventory-transfers/${encodeURIComponent(g.name)}" target="_blank" style="color:#0d6efd;">${esc(g.name)}</a></td>
					<td>${esc(g.docnum||'—')}</td><td>${esc(g.uniware_po_id||'—')}</td>
					<td style="color:#6c757d;">${esc(frappe.datetime.prettyDate(g.modified))}</td>
				</tr>`).join('')}</tbody></table></div>`);
		}
		render_recon_pagination('#recon-grn-pagination', RECON_GRN_PAGE, grn.length,
			function () { if (RECON_GRN_PAGE > 1) { RECON_GRN_PAGE -= 1; render_reconciliation(data); } },
			function () { if (RECON_GRN_PAGE * RECON_PAGE_SIZE < grn.length) { RECON_GRN_PAGE += 1; render_reconciliation(data); } }
		);

		const inv = data.inventory_drift || [];
		const $inv = $(wrapper).find('#recon-inv-drift');
		if (!inv.length) { $inv.html(ok_html); }
		else {
			const inv_pages = Math.max(1, Math.ceil(inv.length / RECON_PAGE_SIZE));
			if (RECON_INV_PAGE > inv_pages) RECON_INV_PAGE = inv_pages;
			const inv_slice = inv.slice((RECON_INV_PAGE - 1) * RECON_PAGE_SIZE, RECON_INV_PAGE * RECON_PAGE_SIZE);
			$inv.html(`<div style="font-size:12px;color:#856404;margin-bottom:8px;font-weight:600;">${inv.length} transfer(s) stalled.</div>
				<div style="overflow-x:auto;"><table class="table table-bordered" style="margin:0;font-size:12px;">
				<thead><tr><th>Transfer</th><th>Doc Num</th><th>Status</th><th>Error</th><th>Modified</th></tr></thead>
				<tbody>${inv_slice.map(g => `<tr>
					<td><a href="/app/sap-inventory-transfers/${encodeURIComponent(g.name)}" target="_blank" style="color:#0d6efd;">${esc(g.name)}</a></td>
					<td>${esc(g.docnum||'—')}</td><td>${status_pill(g.unicommerce_sync_status)}</td>
					<td style="color:#6c757d;font-size:11px;">${esc((g.comments||'').substring(0,70))}</td>
					<td style="color:#6c757d;">${esc(frappe.datetime.prettyDate(g.modified))}</td>
				</tr>`).join('')}</tbody></table></div>`);
		}
		render_recon_pagination('#recon-inv-pagination', RECON_INV_PAGE, inv.length,
			function () { if (RECON_INV_PAGE > 1) { RECON_INV_PAGE -= 1; render_reconciliation(data); } },
			function () { if (RECON_INV_PAGE * RECON_PAGE_SIZE < inv.length) { RECON_INV_PAGE += 1; render_reconciliation(data); } }
		);
	}

	// ─── Test Connections ─────────────────────────────────────────────────────

	$(wrapper).find('#btn-test-conn').on('click', function () {
		frappe.show_alert({ message: 'Testing connections…', indicator: 'blue' });
		frappe.call({
			method: 'khanal_tech_integrations.unicommerce.health.check_connections',
			freeze: true, freeze_message: 'Connecting…',
			callback: function (r) {
				if (!r.message) return;
				const s = r.message;
				const sap_ok = s.sap_login && s.sap_login.ok;
				const uc_ok  = s.uc_login  && s.uc_login.ok;
				frappe.msgprint({
					title: 'Connection Test Results',
					indicator: sap_ok && uc_ok ? 'green' : 'red',
					message: `<div style="display:flex;flex-direction:column;gap:12px;margin-top:8px;">
						${conn_row('SAP B1 Service Layer', sap_ok, s.sap_login && s.sap_login.message)}
						${conn_row('Unicommerce API',      uc_ok,  s.uc_login  && s.uc_login.message)}
					</div>`,
				});
				render_health(s);
			},
		});
	});

	function conn_row(label, ok, msg) {
		return `<div style="background:${ok?'#d4edda':'#f8d7da'};border:1px solid ${ok?'#c3e6cb':'#f5c6cb'};border-radius:6px;padding:12px 16px;">
			<span style="font-size:1.1rem;font-weight:700;color:${ok?'#155724':'#721c24'};margin-right:10px;">${ok?'✓':'✗'}</span>
			<strong style="font-size:13px;">${esc(label)}:</strong>
			<span style="color:${ok?'#155724':'#721c24'};font-weight:600;"> ${ok?'Connected':'Failed'}</span>
			${msg ? `<div style="font-size:11px;color:#6c757d;margin-top:4px;">${esc(msg)}</div>` : ''}
		</div>`;
	}

	// ─── Bindings + Init ──────────────────────────────────────────────────────

	$(wrapper).find('#btn-refresh').on('click', load_dashboard);
	$(wrapper).find('#btn-guardrail-refresh').on('click', function () {
		save_guardrail_filter();
		load_guardrails();
	});
	$(wrapper).find('#guardrail-filter').on('change', function () {
		save_guardrail_filter();
		load_guardrails();
	});
	$(wrapper).find('#btn-inventory-match').on('click', () => frappe.set_route('unicommerce-inventory-match'));
	$(wrapper).find('#btn-settings').on('click', () => frappe.set_route('Form', 'Unicommerce Settings'));
	$(wrapper).find('#btn-load-failures').on('click', function () { FAILURES_PAGE = 1; load_failures(); });
	$(wrapper).find('#btn-failures-select-all').on('click', function () {
		const $checks = $(wrapper).find('.uc-failure-select');
		if (!$checks.length) return;
		const all_checked = $checks.length === $checks.filter(':checked').length;
		$checks.prop('checked', !all_checked);
		$(this).text(all_checked ? 'Select All' : 'Unselect All');
	});
	$(wrapper).find('#btn-failures-bulk-queue').on('click', function () { run_failure_bulk_retry('queue'); });
	$(wrapper).find('#btn-failures-bulk-now').on('click', function () { run_failure_bulk_retry('now'); });
	$(wrapper).find('#btn-analyze-return-ids').on('click', function () {
		const $btn = $(this);
		const orig = $btn.text();
		$btn.prop('disabled', true).text('Analyzing…');
		// Dynamic last-30-day window so this button never needs manual date updates.
		const _today = frappe.datetime.get_today();
		const _from  = frappe.datetime.add_days(_today, -30);
		frappe.call({
			method: API + '.ops_analyze_return_id_extraction',
			args: { from_date: _from, to_date: _today, limit: 300 },
			freeze: false,
			callback: function (r) {
				$btn.prop('disabled', false).text(orig);
				const d = r.message || {};
				frappe.msgprint({
					title: 'Return ID Extraction Analysis',
					indicator: Number(d.missing_ids || 0) > 0 ? 'orange' : 'green',
					message: `
						<div style="font-size:12px;line-height:1.7;">
							<div><strong>Fetched:</strong> ${esc(d.fetched || 0)}</div>
							<div><strong>Extracted OK:</strong> ${esc(d.extracted_ok || 0)}</div>
							<div><strong>Missing IDs:</strong> ${esc(d.missing_ids || 0)}</div>
							<div><strong>Parent Found:</strong> ${esc(d.parent_found || 0)}</div>
						</div>
					`,
				});
			},
			error: function () {
				$btn.prop('disabled', false).text(orig);
				frappe.show_alert({ message: 'Return ID analysis failed', indicator: 'red' }, 5);
			},
		});
	});
	$(wrapper).find('#failures-stage-filter').on('change', function () { FAILURES_PAGE = 1; load_failures(); });

	$(wrapper).find('#btn-coverage-refresh').on('click', load_coverage);
	// Load Order Coverage lazily the first time the user opens the More Tools
	// drawer — the query is ~50 ms but there is no need to pay it on page
	// load if the operator never scrolls down.
	let _coverage_loaded = false;
	$(wrapper).find('#drawer-more').on('toggle', function () {
		if (this.open && !_coverage_loaded) {
			_coverage_loaded = true;
			load_coverage();
		}
	});

	load_saved_guardrail_filter();
	load_saved_cn_filter();
	load_page_size_settings();
	load_gst_pivot_settings();
	render_monitoring_panels();
	load_dashboard();
	load_batch_status();
	load_analytics();
	// If the operator left a pre-validate job running and refreshed the
	// page, reattach the progress UI and resume polling.
	prevalidate_attach_if_running();

	// ─── Auto-refresh ─────────────────────────────────────────────────────────
	// Refresh the overview and failures every 2 minutes so the ops team can leave
	// this page open as a monitor without manually hitting Refresh.
	const AUTO_REFRESH_MS = 2 * 60 * 1000;
	let _auto_refresh_timer = setInterval(function () {
		// Only refresh if the page is visible (don't waste requests on hidden tabs).
		if (document.visibilityState === 'visible') {
			load_dashboard();
			// Re-load batch status only if the section is visible (user scrolled to it).
			const batchWrap = document.getElementById('batch-table-wrap');
			if (batchWrap && batchWrap.style.display !== 'none') {
				load_batch_status();
			}
		}
	}, AUTO_REFRESH_MS);

	// Stop all timers when Frappe navigates away from this page.
	$(wrapper).on('remove', function () {
		clearInterval(_auto_refresh_timer);
		stop_gst_recon_poll();
	});

	// ═══ Step 5 · Inward Inventory (SAP → UC PO + GRN) ══════════════════════

	const INWARD_STATUS_BADGE = {
		PENDING: `<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
			font-size:11px;font-weight:700;background:#fee2e2;color:#b91c1c;">
			⬤ No PO</span>`,
		PO_CREATED: `<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
			font-size:11px;font-weight:700;background:#dbeafe;color:#1d4ed8;">
			⬤ PO Created</span>`,
		GRN_PARTIAL: `<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
			font-size:11px;font-weight:700;background:#fef9c3;color:#92400e;">
			⬤ GRN Partial</span>`,
		GRN_COMPLETED: `<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;
			font-size:11px;font-weight:700;background:#dcfce7;color:#15803d;">
			✓ GRN Done</span>`,
	};

	function _render_inward_summary_cards(s) {
		$('#inward-count-total').text(s.total || 0);
		$('#inward-count-pending').text(s.pending || 0);
		$('#inward-count-po').text(s.po_created || 0);
		$('#inward-count-partial').text(s.grn_partial || 0);
		$('#inward-count-done').text(s.grn_completed || 0);
		$('#inward-summary-cards').show();
		// Enable "Process All" only if there are pending items
		$('#btn-inward-process-all').prop('disabled', (s.pending || 0) === 0);
	}

	function _render_inward_table(rows) {
		if (!rows || !rows.length) {
			$('#inward-tbody').html(
				'<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:24px;">' +
				'No inward transfers (→ EC-FG) found in this date range.</td></tr>'
			);
			$('#inward-table-wrap').show();
			return;
		}
		const html = rows.map(row => {
			const badge = INWARD_STATUS_BADGE[row.ui_status] ||
				`<span style="font-size:11px;color:var(--text-muted);">${esc(row.ui_status)}</span>`;
			const canProcess = row.ui_status === 'PENDING' || row.ui_status === 'PO_CREATED' || row.ui_status === 'GRN_PARTIAL';
			const btnLabel = row.ui_status === 'PENDING' ? 'Process' : 'Retry';
			const actionBtn = canProcess
				? `<button class="btn btn-xs btn-primary btn-inward-process"
					data-docname="${esc(row.name)}"
					title="Creates UC PO (if missing) and GRN(s) for this transfer — writes to live Unicommerce">
					${btnLabel}</button>`
				: `<span style="font-size:11px;color:var(--ok);">✓ Done</span>`;
			const comments = (row.comments || '').trim();
			const commentCell = comments
				? `<span style="color:var(--bad);font-size:10px;" title="${esc(comments)}">⚠ ${esc(comments.slice(0,40))}${comments.length>40?'…':''}</span>`
				: '';
			const grnsDisplay = (row.grn_nos || '').trim()
				? `<span style="font-family:monospace;font-size:11px;" title="${esc(row.grn_nos)}">${esc(row.grn_nos.split(',').slice(0,2).join(', ') + (row.grn_nos.split(',').length > 2 ? ' …' : ''))}</span>`
				: `<span style="color:var(--text-muted);">—</span>`;
			return `<tr>
				<td><strong>${esc(row.docnum || row.name)}</strong>${commentCell ? '<br>' + commentCell : ''}</td>
				<td style="white-space:nowrap;">${esc(row.docdate || '')}</td>
				<td><span class="uc-chip" style="font-size:11px;">${esc(row.fromwarehouse || '—')}</span></td>
				<td style="font-family:monospace;font-size:11px;">${row.po_code ? esc(row.po_code) : '<span style="color:var(--text-muted);">—</span>'}</td>
				<td>${grnsDisplay}</td>
				<td>${badge}</td>
				<td style="text-align:center;">${actionBtn}</td>
			</tr>`;
		}).join('');
		$('#inward-tbody').html(html);
		$('#inward-table-wrap').show();
		$('#inward-last-refreshed').text('Last refreshed: ' + new Date().toLocaleTimeString());
	}

	function _show_inward_process_result(docname, d) {
		let html;
		if (d.success) {
			const grns = (d.grn_codes || []);
			html = `<div style="padding:12px 16px;border:1px solid #bbf7d0;border-radius:var(--radius-sm);background:#f0fdf4;font-size:12px;">
				<strong style="color:#15803d;">✓ Transfer ${esc(docname)} synced to Unicommerce</strong><br>
				<span style="color:var(--text-muted);">
					PO: <code>${esc(d.po_code || '—')}</code> &nbsp;·&nbsp;
					GRN(s) created: <code>${grns.length ? esc(grns.join(', ')) : '0'}</code>
					${d.status ? ' &nbsp;·&nbsp; Status: <strong>' + esc(d.status) + '</strong>' : ''}
				</span>
				${(d.errors||[]).length ? `<br><span style="color:#92400e;">Warnings: ${esc((d.errors||[]).slice(0,3).join('; '))}</span>` : ''}
			</div>`;
		} else {
			html = `<div style="padding:12px 16px;border:1px solid #fca5a5;border-radius:var(--radius-sm);background:#fff5f5;font-size:12px;">
				<strong style="color:#b91c1c;">✗ Failed: ${esc(docname)}</strong><br>
				<span style="color:var(--text-muted);">${esc(d.message || 'Unknown error')}</span>
			</div>`;
		}
		$('#inward-process-result').html(html).show();
	}

	function load_inward_transfers() {
		const days = parseInt($('#inward-days').val() || '30', 10);
		$('#inward-status').html('<em>Loading transfers…</em>');
		$('#btn-inward-refresh').prop('disabled', true).text('Loading…');
		$('#inward-process-result').hide();

		frappe.call({
			method: 'khanal_tech_integrations.unicommerce.api.ops.ops_inward_transfer_list',
			args: { days },
			callback(r) {
				$('#btn-inward-refresh').prop('disabled', false).text('↻ Refresh List');
				const d = r.message || {};
				if (d.error) {
					$('#inward-status').html(`<span style="color:var(--bad);">Error: ${esc(d.error)}</span>`);
					return;
				}
				const rows = d.rows || [];
				const s = d.summary || {};
				const pendingCount = s.pending || 0;
				$('#inward-status').html(
					`Found <strong>${rows.length}</strong> transfer(s) in last <strong>${days}</strong> days.` +
					(pendingCount > 0
						? ` <span style="color:#b91c1c;font-weight:700;">${pendingCount} need processing.</span>`
						: ' <span style="color:#15803d;">All up to date.</span>')
				);
				_render_inward_summary_cards(s);
				_render_inward_table(rows);
			},
			error() {
				$('#btn-inward-refresh').prop('disabled', false).text('↻ Refresh List');
				$('#inward-status').html('<span style="color:var(--bad);">Failed to load. Check error log.</span>');
			},
		});
	}

	function _process_single_inward($btn, docname) {
		$btn.prop('disabled', true).text('…');
		frappe.call({
			method: 'khanal_tech_integrations.unicommerce.api.ops.ops_process_inward_transfer',
			args: { docname },
			callback(r) {
				const d = r.message || {};
				_show_inward_process_result(docname, d);
				// Always refresh the list so the row status updates
				load_inward_transfers();
			},
			error() {
				$btn.prop('disabled', false).text('Retry');
				frappe.show_alert({ message: 'Request failed — check error log', indicator: 'red' }, 6);
			},
		});
	}

	$('#btn-inward-refresh').on('click', load_inward_transfers);

	$('#btn-inward-process-all').on('click', function () {
		const days = parseInt($('#inward-days').val() || '30', 10);
		const pending = parseInt($('#inward-count-pending').text() || '0', 10);
		frappe.confirm(
			`<div style="line-height:1.7;font-size:13px;">
				<strong>Process All Pending Inward Transfers</strong><br><br>
				This will queue a background job to create <strong>UC Purchase Orders and GRNs</strong>
				for all <strong>${pending} pending</strong> inward transfers (→ EC-FG) from the last
				<strong>${days} days</strong>.<br><br>
				<span style="color:#92400e;font-weight:600;">⚠ This writes to live Unicommerce.</span>
				Only proceed if all pending transfers are fully approved in SAP B1.
			</div>`,
			() => {
				frappe.call({
					method: 'khanal_tech_integrations.unicommerce.api.ops.ops_process_pending_inward_transfers',
					args: { days },
					callback(r) {
						const d = r.message || {};
						if (d.queued) {
							frappe.show_alert({
								message: `Background job queued for ${days}-day range. Refresh the list in about 1 minute to see updated statuses.`,
								indicator: 'blue',
							}, 8);
						} else {
							frappe.show_alert({ message: d.message || 'Queue failed', indicator: 'red' }, 6);
						}
					},
				});
			}
		);
	});

	// Per-row Process / Retry button (event delegation — rows are rendered dynamically)
	$(wrapper).on('click', '.btn-inward-process', function () {
		const $btn = $(this);
		const docname = $btn.data('docname');
		if (!docname) return;
		const btnLabel = $btn.text().trim();
		frappe.confirm(
			`<div style="line-height:1.7;font-size:13px;">
				<strong>${btnLabel === 'Retry' ? 'Retry' : 'Process'} Transfer: ${esc(docname)}</strong><br><br>
				This will:
				<ul style="margin:8px 0 0 16px;padding:0;">
					<li>Create a <strong>Purchase Order</strong> in Unicommerce (if not already done)</li>
					<li>Create <strong>GRN(s)</strong> in Unicommerce for each batch line</li>
				</ul><br>
				<span style="color:#92400e;font-weight:600;">⚠ This writes to live Unicommerce.</span>
				Ensure the SAP Inventory Transfer is fully approved before proceeding.
			</div>`,
			() => _process_single_inward($btn, docname)
		);
	});

	// ── Manual UC PO → GRN ───────────────────────────────────────────────────

	$('#btn-manual-po-lookup').on('click', function () {
		const po_code = ($('#manual-po-code').val() || '').trim();
		if (!po_code) {
			frappe.show_alert({ message: 'Enter a UC PO code first (e.g. PO0026)', indicator: 'orange' }, 4);
			$('#manual-po-code').focus();
			return;
		}
		const $btn = $(this);
		$btn.prop('disabled', true).text('Looking up…');
		$('#manual-po-result').hide();
		$('#manual-grn-result').hide();
		$('#btn-manual-po-grn').prop('disabled', true);

		frappe.call({
			method: 'khanal_tech_integrations.unicommerce.api.ops.ops_uc_po_details',
			args: { po_code },
			callback(r) {
				$btn.prop('disabled', false).text('🔍 Look Up PO');
				const d = r.message || {};
				if (!d.success) {
					$('#manual-po-info').html(
						`<span style="color:#b91c1c;">
							✗ Could not find PO <strong>${esc(po_code)}</strong>: ${esc(d.error || 'not found in Unicommerce')}
						</span>`
					);
					$('#manual-po-result').show();
					return;
				}
				const items = d.items || [];
				const statusColor = d.status_code === 'APPROVED' ? '#15803d' : '#92400e';
				$('#manual-po-info').html(
					`<div style="display:flex;gap:20px;flex-wrap:wrap;align-items:center;">
						<div><span style="font-size:11px;color:var(--text-muted);">PO CODE</span><br>
							<strong style="font-family:monospace;">${esc(d.po_code)}</strong></div>
						<div><span style="font-size:11px;color:var(--text-muted);">STATUS</span><br>
							<strong style="color:${statusColor};">${esc(d.status_code || '—')}</strong></div>
						<div><span style="font-size:11px;color:var(--text-muted);">VENDOR</span><br>
							<strong>${esc(d.vendor_name || '—')}</strong></div>
						<div><span style="font-size:11px;color:var(--text-muted);">ITEMS</span><br>
							<strong>${items.length}</strong></div>
					</div>`
				);
				const itemRows = items.length
					? items.map(it =>
						`<tr>
							<td style="font-family:monospace;">${esc(it.sku || '')}</td>
							<td style="text-align:right;font-weight:600;">${esc(it.quantity || 0)}</td>
						</tr>`).join('')
					: '<tr><td colspan="2" style="text-align:center;color:var(--text-muted);padding:12px;">No items found</td></tr>';
				$('#manual-po-tbody').html(itemRows);
				$('#manual-po-result').show();
				$('#btn-manual-po-grn').prop('disabled', items.length === 0);
			},
			error() {
				$btn.prop('disabled', false).text('🔍 Look Up PO');
				frappe.show_alert({ message: 'PO lookup failed — check error log', indicator: 'red' }, 5);
			},
		});
	});

	// Allow pressing Enter in the PO code input to trigger lookup
	$('#manual-po-code').on('keydown', function (e) {
		if (e.key === 'Enter') $('#btn-manual-po-lookup').trigger('click');
	});

	$('#btn-manual-po-grn').on('click', function () {
		const po_code = ($('#manual-po-code').val() || '').trim();
		if (!po_code) return;
		const $btn = $(this);
		frappe.confirm(
			`<div style="line-height:1.7;font-size:13px;">
				<strong>Create GRN for UC PO: ${esc(po_code)}</strong><br><br>
				This will create one or more <strong>Inflow Receipt (GRN)</strong> documents in
				Unicommerce against PO <strong>${esc(po_code)}</strong>, receiving all listed items.<br><br>
				<span style="color:#92400e;">
					Since this PO was created manually in Unicommerce (no SAP source), batch numbers
					will be set to <code>NA</code>.
				</span><br><br>
				<span style="color:#92400e;font-weight:600;">⚠ This writes to live Unicommerce.</span> Proceed?
			</div>`,
			() => {
				$btn.prop('disabled', true).text('Creating GRN…');
				$('#manual-grn-result').hide();
				frappe.call({
					method: 'khanal_tech_integrations.unicommerce.api.ops.ops_create_grn_for_manual_po',
					args: { po_code },
					callback(r) {
						$btn.prop('disabled', false).text('✚ Create GRN');
						const d = r.message || {};
						const grns = (d.grn_codes || []);
						const errs = (d.errors || []);
						let html;
						if (d.success) {
							html = `<div style="padding:14px 16px;border:1px solid #bbf7d0;border-radius:var(--radius-sm);background:#f0fdf4;font-size:12px;">
								<div style="font-weight:700;color:#15803d;font-size:13px;margin-bottom:6px;">
									✓ GRN(s) created successfully for PO ${esc(po_code)}
								</div>
								<div style="color:var(--text-muted);">
									GRN Code(s): <code>${esc(grns.join(', '))}</code>
								</div>
								${errs.length ? `<div style="margin-top:6px;color:#92400e;">
									<strong>Warnings (${errs.length}):</strong><br>
									${errs.slice(0,5).map(e => `<div>• ${esc(e)}</div>`).join('')}
								</div>` : ''}
								<div style="margin-top:10px;font-size:11px;color:var(--text-muted);">
									The stock has been received in Unicommerce. Verify in UC under
									<em>Inbound → Inflow Receipts</em>.
								</div>
							</div>`;
						} else {
							html = `<div style="padding:14px 16px;border:1px solid #fca5a5;border-radius:var(--radius-sm);background:#fff5f5;font-size:12px;">
								<div style="font-weight:700;color:#b91c1c;font-size:13px;margin-bottom:6px;">
									✗ GRN creation failed for PO ${esc(po_code)}
								</div>
								<div style="color:var(--text-muted);">${esc(d.message || 'Unknown error')}</div>
								${errs.length ? `<div style="margin-top:6px;">
									${errs.slice(0,5).map(e => `<div style="color:#b91c1c;">• ${esc(e)}</div>`).join('')}
								</div>` : ''}
								<div style="margin-top:10px;font-size:11px;color:var(--text-muted);">
									Check <em>Error Log</em> in Frappe for details. You can safely retry — no duplicate PO will be created.
								</div>
							</div>`;
						}
						$('#manual-grn-result').html(html).show();
					},
					error() {
						$btn.prop('disabled', false).text('✚ Create GRN');
						frappe.show_alert({ message: 'Request failed — check error log', indicator: 'red' }, 5);
					},
				});
			}
		);
	});
};
