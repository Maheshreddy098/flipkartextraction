<template>
  <div :class="shellClass">
    <div class="mx-auto w-full max-w-[1480px] space-y-5 px-4 py-5 sm:px-6 lg:px-8">
      <section :class="heroClass">
        <div class="grid gap-6 xl:grid-cols-[1.35fr,0.95fr]">
          <div class="space-y-5">
            <div class="flex flex-wrap items-center gap-3">
              <div :class="badgeClass">
                Live Control Tower
              </div>
              <div :class="pillClass">
                Generated {{ dashboard.generated_at || "-" }}
              </div>
              <div :class="pillClass">
                Last refresh {{ generatedTime }}
              </div>
            </div>

            <div class="space-y-3">
              <div class="flex flex-wrap items-start justify-between gap-4">
                <div class="min-w-0">
                  <h1 :class="heroTitleClass">Unicommerce x SAP Control Tower</h1>
                  <p :class="heroTextClass">
                    Pull, post, monitor, reconcile, and analyze the middleware with live operational data.
                    The page now stays inside the layout, supports light and dark mode, and renders queue, GST, geography, failures, and reconciliation from the real ops API.
                  </p>
                </div>
                <button :class="themeToggleClass" @click="toggleTheme">
                  {{ isDark ? "Light Mode" : "Dark Mode" }}
                </button>
              </div>

              <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div
                  v-for="signal in signalCards"
                  :key="signal.title"
                  :class="signal.cardClass">
                  <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {{ signal.title }}
                  </div>
                  <div :class="signal.valueClass">
                    {{ signal.value }}
                  </div>
                  <div class="text-sm text-slate-500">
                    {{ signal.caption }}
                  </div>
                  <div :class="signal.detailClass">
                    {{ signal.detail }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div :class="controlPanelClass">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 class="text-lg font-semibold">Filters and Controls</h2>
                <p class="mt-1 text-sm text-slate-400">
                  Refresh live metrics, swap date windows, and monitor worker health.
                </p>
              </div>
              <button :class="toggleAutoClass" @click="toggleAutoRefresh">
                Auto refresh {{ autoRefreshEnabled ? "On" : "Off" }}
              </button>
            </div>

            <div class="grid gap-3 sm:grid-cols-2">
              <label :class="controlInputShellClass">
                <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">Date From</div>
                <input v-model="filters.startDate" type="date" :class="controlInputClass" />
              </label>
              <label :class="controlInputShellClass">
                <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">Date To</div>
                <input v-model="filters.endDate" type="date" :class="controlInputClass" />
              </label>
            </div>

            <div class="grid gap-3 sm:grid-cols-4">
              <button
                :class="primaryButtonClass"
                :disabled="loading.dashboard"
                @click="loadDashboard()">
                {{ loading.dashboard ? "Refreshing..." : "Refresh Dashboard" }}
              </button>
              <button :class="secondaryButtonClass" @click="setRollingRange(30)">Last 30 Days</button>
              <button :class="secondaryButtonClass" @click="setMonthRange(0)">This Month</button>
              <button :class="secondaryButtonClass" @click="setMonthRange(-1)">Prev Month</button>
            </div>

            <div class="grid gap-3 sm:grid-cols-2">
              <div
                v-for="health in connectivityCards"
                :key="health.label"
                :class="health.cardClass">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">{{ health.label }}</div>
                    <div class="mt-2 text-lg font-semibold">{{ health.status }}</div>
                  </div>
                  <div :class="health.badgeClass">
                    {{ health.badge }}
                  </div>
                </div>
                <div class="mt-3 text-sm text-slate-500">
                  {{ health.message }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <article v-for="card in kpiCards" :key="card.title" :class="metricCardClass">
          <div class="flex items-start justify-between gap-3">
            <div class="text-[11px] uppercase tracking-[0.18em] text-slate-400">
              {{ card.title }}
            </div>
            <div :class="card.dotClass" class="h-2.5 w-2.5 rounded-full"></div>
          </div>
          <div :class="metricValueClass">
            {{ card.value }}
          </div>
          <div class="mt-3 flex items-center justify-between gap-3 text-xs">
            <span class="text-slate-500">{{ card.caption }}</span>
            <span :class="card.accent">{{ card.detail }}</span>
          </div>
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1.4fr,0.95fr]">
        <article :class="panelClass">
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Pipeline Velocity</h2>
              <p :class="sectionTextClass">Queue movement across fetched, ready, posted, and blocked states.</p>
            </div>
            <div :class="chipClass">14-day trend</div>
          </div>
          <div :class="chartPanelClass">
            <div class="h-[360px] min-w-0">
              <Bar v-if="timelineHasData" :data="timelineChartData" :options="timelineChartOptions" />
              <div v-else :class="emptyStateClass">No timeline data yet.</div>
            </div>
          </div>
        </article>

        <div class="grid gap-4">
          <article :class="panelClass">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 :class="sectionTitleClass">GST Mix</h2>
                <p :class="sectionTextClass">IGST versus CGST + SGST using posted staged orders.</p>
              </div>
              <div :class="chipClass">{{ num(totalPostedCount) }} invoices</div>
            </div>
            <div class="grid gap-4 lg:grid-cols-[0.95fr,1.05fr]">
              <div class="h-[220px] min-w-0">
                <Doughnut v-if="taxSplitHasData" :data="taxSplitChartData" :options="taxSplitChartOptions" />
                <div v-else :class="emptyStateClass">No posted invoices in range.</div>
              </div>
              <div class="grid gap-3">
                <div :class="subMetricBlueClass">
                  <div class="text-[11px] uppercase tracking-[0.18em] text-blue-700">IGST</div>
                  <div class="mt-2 text-2xl font-semibold text-slate-900">{{ num(analytics.igst?.cnt) }}</div>
                  <div class="text-sm text-slate-600">{{ money(analytics.igst?.tax_total) }}</div>
                </div>
                <div :class="subMetricVioletClass">
                  <div class="text-[11px] uppercase tracking-[0.18em] text-violet-700">CGST + SGST</div>
                  <div class="mt-2 text-2xl font-semibold text-slate-900">{{ num(analytics.cgst_sgst?.cnt) }}</div>
                  <div class="text-sm text-slate-600">{{ money(analytics.cgst_sgst?.tax_total) }}</div>
                </div>
              </div>
            </div>
          </article>

          <article :class="panelClass">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 :class="sectionTitleClass">Worker Health</h2>
                <p :class="sectionTextClass">Latest scheduled worker outcomes and execution freshness.</p>
              </div>
            </div>
            <div class="space-y-3">
              <div
                v-for="worker in workerRows"
                :key="worker.name"
                :class="workerRowClass">
                <div class="min-w-0">
                  <div :class="bodyTextClass">{{ worker.label }}</div>
                  <div class="text-xs text-slate-500">{{ worker.at }}</div>
                </div>
                <div :class="worker.badgeClass">{{ worker.status }}</div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1.24fr,0.76fr]">
        <article :class="panelClass">
          <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Operations Deck</h2>
              <p :class="sectionTextClass">Manual pulls, queue promotion, SAP posting, GRN, and inventory sync.</p>
            </div>
            <div :class="attentionChipClass">Batch Hold {{ num(batchValidation.batch_hold_count) }}</div>
          </div>

          <div class="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
            <button
              v-for="action in actions"
              :key="action.worker"
              :class="operationCardClass"
              :disabled="Boolean(loading.actions[action.worker])"
              @click="runWorker(action)">
              <div class="mb-4 flex items-start justify-between gap-3">
                <div>
                  <div :class="action.kickerClass" class="text-[11px] uppercase tracking-[0.18em]">{{ action.group }}</div>
                  <div :class="bodyTitleClass">{{ action.label }}</div>
                </div>
                <div :class="action.dotClass" class="mt-1 h-3 w-3 rounded-full"></div>
              </div>
              <div class="text-sm leading-6 text-slate-500">{{ action.description }}</div>
              <div :class="actionFooterClass">
                {{ loading.actions[action.worker] ? "Running..." : action.cta }}
              </div>
            </button>
          </div>

          <div class="mt-5 grid gap-4 lg:grid-cols-[0.78fr,1.22fr]">
            <div :class="softPanelClass">
              <div class="mb-3 flex items-center justify-between gap-3">
                <h3 :class="subSectionTitleClass">Queue Snapshot</h3>
                <button class="text-xs text-cyan-600 hover:text-cyan-500" @click="loadDashboard()">Refresh</button>
              </div>
              <div class="space-y-3">
                <div v-for="queue in queueCards" :key="queue.label" :class="queueRowClass">
                  <span class="text-sm text-slate-500">{{ queue.label }}</span>
                  <span :class="queue.valueClass">{{ queue.value }}</span>
                </div>
                <div :class="noteCardClass">
                  Fetched rows are promoted to ready automatically before invoice posting, so scheduled runs no longer stall on fetched-only batches.
                </div>
              </div>
            </div>

            <div :class="logPanelClass">
              <div class="mb-3 flex items-center justify-between gap-3">
                <h3 class="text-sm font-semibold">Action Log</h3>
                <button class="text-xs text-slate-400 hover:text-slate-200" @click="actionLog = ''">Clear</button>
              </div>
              <pre class="max-h-[320px] overflow-auto whitespace-pre-wrap break-words rounded-[18px] bg-black/35 p-4 text-xs leading-6 text-emerald-300">{{ actionLog || "No actions executed in this session." }}</pre>
            </div>
          </div>
        </article>

        <div class="grid gap-4">
          <article :class="panelClass">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 :class="sectionTitleClass">Channel Mix</h2>
                <p :class="sectionTextClass">Posted order count and reconciliation gaps by channel.</p>
              </div>
            </div>
            <div class="h-[290px] min-w-0">
              <Bar v-if="channelHasData" :data="channelChartData" :options="channelChartOptions" />
              <div v-else :class="emptyStateClass">No channel data in range.</div>
            </div>
          </article>

          <article :class="panelClass">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 :class="sectionTitleClass">Regional Summary</h2>
                <p :class="sectionTextClass">Order volume and tax concentration by shipping region.</p>
              </div>
            </div>
            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
              <div
                v-for="region in regionCards"
                :key="region.region"
                :class="regionSummaryCardClass"
                :style="regionStyle(region)">
                <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">{{ region.region }}</div>
                <div class="mt-2 text-2xl font-semibold text-slate-900">{{ num(region.cnt) }}</div>
                <div class="text-sm text-slate-600">{{ money(region.tax_total) }}</div>
                <div class="mt-3 text-[11px] leading-5 text-slate-500">{{ region.states?.slice(0, 4).join(", ") || "No states" }}</div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1.02fr,0.98fr]">
        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Inventory Match</h2>
              <p :class="sectionTextClass">SAP EC-FG stock versus Unicommerce facility inventory for tracked SKUs.</p>
            </div>
            <div :class="chipClass">{{ inventoryParity.source === "live_oitw" ? "Live OITW" : "Snapshot" }}</div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Tracked SKUs</div>
              <div :class="metricValueClass">{{ num(inventoryParity.item_count) }}</div>
            </div>
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Mismatches</div>
              <div class="mt-3 text-3xl font-semibold text-amber-600">{{ num(inventoryParity.mismatch_count) }}</div>
            </div>
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Matched</div>
              <div class="mt-3 text-3xl font-semibold text-emerald-600">{{ num(inventoryParity.matched_count) }}</div>
            </div>
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Net Delta</div>
              <div class="mt-3 text-3xl font-semibold text-cyan-600">{{ num(inventoryParity.total_delta_qty) }}</div>
            </div>
          </div>

          <div class="mt-4" :class="stateTableWrapClass">
            <table class="min-w-full text-sm">
              <thead :class="tableHeadClass">
                <tr>
                  <th class="px-4 py-3">Item</th>
                  <th class="px-4 py-3 text-right">SAP Qty</th>
                  <th class="px-4 py-3 text-right">UC Good Qty</th>
                  <th class="px-4 py-3 text-right">Delta</th>
                  <th class="px-4 py-3 text-right">Batch Drift</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in parityRows.slice(0, 10)" :key="row.item_code" :class="tableRowClass">
                  <td :class="tablePrimaryCellClass">{{ row.item_code }}</td>
                  <td :class="tablePrimaryRightCellClass">{{ num(row.sap_qty) }}</td>
                  <td :class="tablePrimaryRightCellClass">{{ num(row.uc_qty) }}</td>
                  <td class="px-4 py-3 text-right" :class="Math.abs(row.delta_qty || 0) > 0.001 ? 'text-amber-700' : 'text-emerald-700'">
                    {{ num(row.delta_qty) }}
                  </td>
                  <td class="px-4 py-3 text-right" :class="row.batch_mismatch_count ? 'text-red-700' : 'text-slate-500'">
                    {{ num(row.batch_mismatch_count) }}
                  </td>
                </tr>
                <tr v-if="!parityRows.length">
                  <td colspan="5" class="px-4 py-8 text-center text-sm text-slate-500">
                    {{ inventoryParity.message || "No inventory mismatch rows available." }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">EC-FG Transfer Flow</h2>
              <p :class="sectionTextClass">SAP transfers into EC-FG, approved POs, GRNs, and posting failures in Unicommerce.</p>
            </div>
            <div :class="chipClass">{{ num(transferSummary.total_to_ec_fg) }} transfers</div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">To EC-FG</div>
              <div :class="metricValueClass">{{ num(transferSummary.total_to_ec_fg) }}</div>
            </div>
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Approved PO</div>
              <div class="mt-3 text-3xl font-semibold text-cyan-600">{{ num(transferSummary.po_created) }}</div>
            </div>
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Posted to UC</div>
              <div class="mt-3 text-3xl font-semibold text-emerald-600">{{ num(transferSummary.posted_to_unicommerce) }}</div>
            </div>
            <div :class="miniInfoCardClass">
              <div class="text-[11px] uppercase tracking-[0.18em] text-slate-500">Failed / Pending</div>
              <div class="mt-3 text-3xl font-semibold text-amber-600">{{ num(transferSummary.failed) }} / {{ num(transferSummary.pending) }}</div>
            </div>
          </div>

          <div class="mt-4 grid gap-4 lg:grid-cols-[0.94fr,1.06fr]">
            <div :class="chartPanelClass">
              <div class="h-[260px] min-w-0">
                <Bar v-if="transferHasData" :data="transferChartData" :options="transferChartOptions" />
                <div v-else :class="emptyStateClass">No inbound EC-FG transfer rows in this range.</div>
              </div>
            </div>
            <div class="space-y-3">
              <div v-for="row in transferRows.slice(0, 6)" :key="row.name" :class="failureCardClass">
                <div class="flex items-center justify-between gap-3">
                  <div class="min-w-0">
                    <div :class="bodyTextClass">Transfer {{ row.docnum }}</div>
                    <div class="text-xs text-slate-500">{{ row.docdate }} • {{ row.fromwarehouse }} → {{ row.towarehouse }}</div>
                  </div>
                  <div :class="failureBadgeClass(row.unicommerce_sync_status || row.uniware_po_status)" class="rounded-full px-3 py-1 text-xs font-semibold">
                    {{ row.unicommerce_sync_status || row.uniware_po_status || "Pending" }}
                  </div>
                </div>
                <div class="mt-2 text-xs text-slate-500">PO {{ row.uniware_po_id || "Not created" }} • Status {{ row.uniware_po_status || "Not started" }}</div>
                <div class="mt-2 text-xs leading-5 text-slate-600">{{ row.comments || "No error note on this transfer." }}</div>
              </div>
              <div v-if="!transferRows.length" :class="emptyStateClass">No recent inbound EC-FG transfer activity.</div>
            </div>
          </div>
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">India Operations Map</h2>
              <p :class="sectionTextClass">Regional live heat map based on posted orders and tax captured from the real analytics payload.</p>
            </div>
            <div :class="chipClass">Top region {{ topRegion?.region || "NA" }}</div>
          </div>

          <div class="grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
            <div :class="mapPanelClass">
              <svg viewBox="0 0 100 100" class="h-[360px] w-full">
                <defs>
                  <linearGradient id="india-base" x1="0%" x2="100%" y1="0%" y2="100%">
                    <stop offset="0%" :stop-color="isDark ? '#0ea5e9' : '#dbeafe'" stop-opacity="0.18" />
                    <stop offset="100%" :stop-color="isDark ? '#8b5cf6' : '#c4b5fd'" stop-opacity="0.14" />
                  </linearGradient>
                </defs>
                <path
                  d="M41 9c6 2 10 7 10 13 0 6 4 10 9 12 6 2 9 8 7 14-2 5-1 10 2 14 3 4 3 9 0 14-3 4-6 7-8 12-2 5-1 10-4 14-3 5-8 8-13 9-5 1-7 5-7 10 0 4-3 7-7 7-5 0-8-4-8-9 0-5 2-10-1-14-3-5-9-7-12-12-3-5-4-12-1-18 2-5 6-9 11-12 4-2 7-6 9-11 2-7 8-12 13-15z"
                  :fill="'url(#india-base)'"
                  :stroke="isDark ? 'rgba(148,163,184,0.35)' : 'rgba(148,163,184,0.45)'"
                  stroke-width="1.2" />
                <g v-for="node in regionMapNodes" :key="node.region">
                  <circle
                    :cx="node.x"
                    :cy="node.y"
                    :r="node.radius"
                    :fill="node.fill"
                    :stroke="node.stroke"
                    stroke-width="1.6" />
                  <circle
                    :cx="node.x"
                    :cy="node.y"
                    :r="node.radius + 4"
                    :fill="node.ring"
                    fill-opacity="0.18" />
                  <text
                    :x="node.x"
                    :y="node.y - node.radius - 4"
                    text-anchor="middle"
                    font-size="3.2"
                    font-weight="600"
                    :fill="isDark ? '#e2e8f0' : '#0f172a'">
                    {{ node.region }}
                  </text>
                  <text
                    :x="node.x"
                    :y="node.y + 1"
                    text-anchor="middle"
                    font-size="4.1"
                    font-weight="700"
                    :fill="isDark ? '#f8fafc' : '#0f172a'">
                    {{ node.countLabel }}
                  </text>
                  <text
                    :x="node.x"
                    :y="node.y + node.radius + 6"
                    text-anchor="middle"
                    font-size="2.8"
                    :fill="isDark ? '#94a3b8' : '#475569'">
                    {{ node.taxLabel }}
                  </text>
                </g>
              </svg>
            </div>

            <div class="space-y-3">
              <div v-for="node in regionMapNodes" :key="`${node.region}-meta`" :class="mapMetaCardClass">
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div :class="bodyTextClass">{{ node.region }}</div>
                    <div class="text-xs text-slate-500">{{ node.statesLabel }}</div>
                  </div>
                  <div class="text-right">
                    <div :class="tablePrimaryTextClass">{{ node.countLabel }} orders</div>
                    <div class="text-xs text-slate-500">{{ node.taxLabel }}</div>
                  </div>
                </div>
              </div>
              <div :class="noteCardClass">
                Region intensity scales by posted order count. IGST-heavy routes normally show stronger interstate concentration in North, West, and East lanes.
              </div>
            </div>
          </div>
        </article>

        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Daily Tax Trend</h2>
              <p :class="sectionTextClass">Order count and tax movement inside the selected date range.</p>
            </div>
          </div>
          <div :class="chartPanelClass">
            <div class="h-[360px] min-w-0">
              <Line v-if="dailyTrendHasData" :data="dailyTrendChartData" :options="dailyTrendChartOptions" />
              <div v-else :class="emptyStateClass">No daily commercial trend in this range.</div>
            </div>
          </div>
        </article>
      </section>

      <section class="grid gap-4 xl:grid-cols-[0.98fr,1.02fr]">
        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">State Breakdown</h2>
              <p :class="sectionTextClass">Top states by posted order count, GST amount, and reconciliation gaps.</p>
            </div>
            <div :class="chipClass">{{ stateRows.length }} states</div>
          </div>
          <div :class="stateTableWrapClass">
            <table class="min-w-full text-sm">
              <thead :class="tableHeadClass">
                <tr>
                  <th class="px-4 py-3">State</th>
                  <th class="px-4 py-3">Region</th>
                  <th class="px-4 py-3 text-right">Orders</th>
                  <th class="px-4 py-3 text-right">Tax</th>
                  <th class="px-4 py-3 text-right">Gaps</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="state in stateRows.slice(0, 12)" :key="state.state" :class="tableRowClass">
                  <td :class="tablePrimaryCellClass">{{ state.state }}</td>
                  <td class="px-4 py-3 text-slate-500">{{ state.region }}</td>
                  <td :class="tablePrimaryRightCellClass">{{ num(state.cnt) }}</td>
                  <td :class="tablePrimaryRightCellClass">{{ money(state.tax_total) }}</td>
                  <td class="px-4 py-3 text-right" :class="state.gap_count ? 'text-amber-700' : 'text-emerald-700'">{{ num(state.gap_count) }}</td>
                </tr>
                <tr v-if="!stateRows.length">
                  <td colspan="5" class="px-4 py-8 text-center text-sm text-slate-500">No state distribution available.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Failure and Reconciliation Radar</h2>
              <p :class="sectionTextClass">Surface records requiring action before they impact posting quality.</p>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="space-y-3">
              <div class="flex items-center justify-between gap-3">
                <h3 :class="subSectionTitleClass">Recent Failures</h3>
                <div :class="chipClass">{{ num(failureRows.length) }}</div>
              </div>
              <div class="space-y-3">
                <div v-for="row in failureRows.slice(0, 5)" :key="`${row.doctype}-${row.name}`" :class="failureCardClass">
                  <div class="flex items-center justify-between gap-3">
                    <div class="min-w-0">
                      <div :class="bodyTextClass">{{ row.external_id || row.name }}</div>
                      <div class="text-xs text-slate-500">{{ row.stage }} / {{ row.doctype }}</div>
                    </div>
                    <div :class="failureBadgeClass(row.status)" class="rounded-full px-3 py-1 text-xs font-semibold">{{ row.status }}</div>
                  </div>
                  <div class="mt-3 text-xs leading-5 text-slate-600">{{ row.last_error || "No error text captured." }}</div>
                </div>
                <div v-if="!failureRows.length" :class="emptyStateClass">No recent failures.</div>
              </div>
            </div>

            <div class="space-y-3">
              <div class="flex items-center justify-between gap-3">
                <h3 :class="subSectionTitleClass">Reconciliation Radar</h3>
                <div :class="chipClass">{{ num(reconciliationRows.length) }} gaps</div>
              </div>
              <div class="space-y-3">
                <div
                  v-for="gap in reconciliationRows.slice(0, 5)"
                  :key="`${gap.source}-${gap.record_name}-${gap.document_type}`"
                  :class="reconCardClass">
                  <div class="flex items-center justify-between gap-3">
                    <div class="min-w-0">
                      <div :class="bodyTextClass">{{ gap.uc_order_id || gap.record_name }}</div>
                      <div class="text-xs text-slate-500">{{ gap.source }} / {{ gap.document_type }} / {{ gap.channel || "Unknown channel" }}</div>
                    </div>
                    <a :class="openButtonClass" :href="recordHref(gap)" target="_blank" rel="noreferrer">Open</a>
                  </div>
                  <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
                    <div :class="miniInfoCardClass">Tax diff <span class="font-semibold text-amber-700">{{ money(gap.tax_diff) }}</span></div>
                    <div :class="miniInfoCardClass">Unit diff <span class="font-semibold text-orange-700">{{ money(gap.unit_price_diff) }}</span></div>
                  </div>
                </div>
                <div v-if="!reconciliationRows.length" :class="emptyStateClass">No reconciliation gaps in the current dataset.</div>
              </div>
            </div>
          </div>
        </article>
      </section>

      <section :class="panelClass">
        <div class="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 :class="sectionTitleClass">Monthly Tax Reconciliation</h2>
            <p :class="sectionTextClass">Channel-wise monthly taxable value and IGST versus CGST + SGST comparison between staged Unicommerce values and posted SAP invoices.</p>
          </div>
          <div :class="chipClass">{{ monthlyRows.length }} channel-month rows</div>
        </div>

        <div class="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
          <div :class="chartPanelClass">
            <div class="h-[320px] min-w-0">
              <Bar v-if="monthlyHasData" :data="monthlyChartData" :options="monthlyChartOptions" />
              <div v-else :class="emptyStateClass">No monthly reconciliation rows available yet.</div>
            </div>
          </div>

          <div :class="stateTableWrapClass">
            <table class="min-w-full text-sm">
              <thead :class="tableHeadClass">
                <tr>
                  <th class="px-4 py-3">Month</th>
                  <th class="px-4 py-3">Channel</th>
                  <th class="px-4 py-3 text-right">UC Taxable</th>
                  <th class="px-4 py-3 text-right">SAP Taxable</th>
                  <th class="px-4 py-3 text-right">IGST Diff</th>
                  <th class="px-4 py-3 text-right">CGST+SGST Diff</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in monthlyRows.slice(0, 12)" :key="`${row.month}-${row.channel}`" :class="tableRowClass">
                  <td :class="tablePrimaryCellClass">{{ row.month_label }}</td>
                  <td class="px-4 py-3 text-slate-500">{{ row.channel }}</td>
                  <td :class="tablePrimaryRightCellClass">{{ money(row.uc_taxable_total) }}</td>
                  <td :class="tablePrimaryRightCellClass">{{ money(row.sap_taxable_total) }}</td>
                  <td class="px-4 py-3 text-right" :class="Math.abs(row.igst_diff || 0) > 0.01 ? 'text-amber-700' : 'text-emerald-700'">{{ money(row.igst_diff) }}</td>
                  <td class="px-4 py-3 text-right" :class="Math.abs(row.cgst_sgst_diff || 0) > 0.01 ? 'text-amber-700' : 'text-emerald-700'">{{ money(row.cgst_sgst_diff) }}</td>
                </tr>
                <tr v-if="!monthlyRows.length">
                  <td colspan="6" class="px-4 py-8 text-center text-sm text-slate-500">No monthly reconciliation rows available.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section class="grid gap-4 xl:grid-cols-[0.94fr,1.06fr]">
        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Scheduler Feed</h2>
              <p :class="sectionTextClass">Most recent scheduled worker activity in the selected monitoring window.</p>
            </div>
          </div>
          <div class="space-y-3">
            <div v-for="job in activityJobs.slice(0, 7)" :key="job.name" :class="workerRowClass">
              <div class="min-w-0">
                <div :class="bodyTextClass">{{ shortWorker(job.scheduled_job_type) }}</div>
                <div class="text-xs text-slate-500">{{ shortTime(job.creation) }}</div>
              </div>
              <div :class="job.status === 'Complete' ? 'rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700' : 'rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700'">
                {{ job.status }}
              </div>
            </div>
            <div v-if="!activityJobs.length" :class="emptyStateClass">No scheduled jobs in the selected window.</div>
          </div>
        </article>

        <article :class="panelClass">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 :class="sectionTitleClass">Error Feed</h2>
              <p :class="sectionTextClass">Recent middleware exceptions tagged with Unicommerce flows.</p>
            </div>
          </div>
          <div class="space-y-3">
            <div v-for="error in activityErrors.slice(0, 7)" :key="error.name" class="rounded-[22px] border border-red-200 bg-red-50 p-4">
              <div class="flex items-center justify-between gap-3">
                <div :class="bodyTextClass">{{ shortWorker(error.method) }}</div>
                <div class="text-xs text-slate-500">{{ shortTime(error.creation) }}</div>
              </div>
              <div class="mt-2 text-xs leading-5 text-slate-600">{{ error.error }}</div>
            </div>
            <div v-if="!activityErrors.length" :class="emptyStateClass">No recent errors.</div>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue"
import { frappeRequest } from "frappe-ui"
import { Bar, Doughnut, Line } from "vue-chartjs"
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Title,
  Tooltip,
} from "chart.js"

ChartJS.register(CategoryScale, LinearScale, BarElement, ArcElement, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const OPS_API = "khanal_tech_integrations.unicommerce.api.ops"
const THEME_STORAGE_KEY = "unicommerce-dashboard-theme"
const AUTO_REFRESH_STORAGE_KEY = "unicommerce-dashboard-auto-refresh"
const REFRESH_INTERVAL_MS = 60000

const REGION_ORDER = ["North", "West", "Central", "East", "South", "North East", "Other"]
const REGION_COORDINATES = {
  North: { x: 48, y: 18 },
  West: { x: 32, y: 40 },
  Central: { x: 48, y: 49 },
  East: { x: 67, y: 43 },
  South: { x: 44, y: 77 },
  "North East": { x: 81, y: 28 },
  Other: { x: 22, y: 18 },
}

const themeMode = ref(getStoredTheme())
const autoRefreshEnabled = ref(getStoredAutoRefresh())

const filters = reactive({
  startDate: rollingStart(30),
  endDate: rollingEnd(),
})

const loading = reactive({
  dashboard: false,
  actions: {},
})

const dashboard = ref(createDashboardState())
const actionLog = ref("")
let refreshHandle = null

const actions = [
  { worker: "fetch_orders", label: "Pull Orders", cta: "Fetch now", group: "Pull", description: "Stage new and updated Unicommerce orders.", kickerClass: "text-cyan-700", dotClass: "bg-cyan-500" },
  { worker: "promote_fetched_to_ready", label: "Promote Queue", cta: "Advance fetched", group: "Queue", description: "Move fetched rows into ready for SAP posting.", kickerClass: "text-blue-700", dotClass: "bg-blue-500" },
  { worker: "post_invoices", label: "Post Invoices", cta: "Push to SAP", group: "SAP", description: "Post ready orders and verify uncertain SAP responses.", kickerClass: "text-emerald-700", dotClass: "bg-emerald-500" },
  { worker: "fetch_returns", label: "Pull Returns", cta: "Fetch returns", group: "Pull", description: "Stage return records eligible for credit notes.", kickerClass: "text-indigo-700", dotClass: "bg-indigo-500" },
  { worker: "post_credit_notes", label: "Post Credit Notes", cta: "Create credits", group: "SAP", description: "Post staged return credits against parent invoices.", kickerClass: "text-violet-700", dotClass: "bg-violet-500" },
  { worker: "retry_batch_holds", label: "Release Batch Holds", cta: "Re-queue holds", group: "Recovery", description: "Move blocked orders back to ready after stock correction.", kickerClass: "text-amber-700", dotClass: "bg-amber-500" },
  { worker: "sync_grns", label: "Sync GRNs", cta: "Run GRN sync", group: "Warehouse", description: "Push approved PO and GRN activity to Unicommerce.", kickerClass: "text-fuchsia-700", dotClass: "bg-fuchsia-500" },
  { worker: "sync_inventory", label: "Sync Inventory", cta: "Adjust stock", group: "Warehouse", description: "Send SAP transfer adjustments to Unicommerce inventory.", kickerClass: "text-rose-700", dotClass: "bg-rose-500" },
  { worker: "refresh_inventory_parity", label: "Refresh Inventory Match", cta: "Refresh parity", group: "Audit", description: "Rebuild the EC-FG versus Unicommerce mismatch snapshot from live data.", kickerClass: "text-sky-700", dotClass: "bg-sky-500" },
]

const isDark = computed(() => themeMode.value === "dark")
const overview = computed(() => dashboard.value.overview || createDashboardState().overview)
const analytics = computed(() => dashboard.value.analytics || createDashboardState().analytics)
const batchValidation = computed(() => dashboard.value.batch_validation || createDashboardState().batch_validation)
const inventoryParity = computed(() => dashboard.value.inventory_parity || createDashboardState().inventory_parity)
const transferSummary = computed(() => dashboard.value.transfers || createDashboardState().transfers)
const monthlyReconciliation = computed(() => dashboard.value.monthly_reconciliation || createDashboardState().monthly_reconciliation)
const reconciliationRows = computed(() => dashboard.value.reconciliation?.invoice_gaps || [])
const failureRows = computed(() => dashboard.value.failures?.rows || [])
const activityJobs = computed(() => dashboard.value.activity?.jobs || [])
const activityErrors = computed(() => dashboard.value.activity?.errors || [])
const timelineRows = computed(() => dashboard.value.timeline || [])
const dailyRows = computed(() => analytics.value.daily || [])
const channelRows = computed(() => analytics.value.by_channel || [])
const stateRows = computed(() => analytics.value.by_state || [])
const parityRows = computed(() => inventoryParity.value.rows || [])
const transferRows = computed(() => transferSummary.value.rows || [])
const transferDailyRows = computed(() => transferSummary.value.daily || [])
const monthlyRows = computed(() => monthlyReconciliation.value.rows || [])
const totalPostedCount = computed(() => analytics.value.total?.cnt || 0)
const generatedTime = computed(() => shortTime(dashboard.value.generated_at || overview.value.generated_at))

const shellClass = computed(() =>
  isDark.value
    ? "min-h-full w-full overflow-x-hidden bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.14),transparent_30%),linear-gradient(180deg,#020617,#0f172a)] text-slate-100 transition-colors duration-300"
    : "min-h-full w-full overflow-x-hidden bg-[radial-gradient(circle_at_top,rgba(125,211,252,0.24),transparent_28%),linear-gradient(180deg,#f8fafc,#e2e8f0)] text-slate-900 transition-colors duration-300"
)

const heroClass = computed(() =>
  isDark.value
    ? "overflow-hidden rounded-[30px] border border-slate-800 bg-slate-900/80 px-5 py-5 shadow-[0_28px_80px_rgba(2,6,23,0.45)] backdrop-blur sm:px-6"
    : "overflow-hidden rounded-[30px] border border-white/80 bg-white/90 px-5 py-5 shadow-[0_22px_70px_rgba(148,163,184,0.18)] backdrop-blur sm:px-6"
)

const panelClass = computed(() =>
  isDark.value
    ? "min-w-0 rounded-[28px] border border-slate-800 bg-slate-900/80 p-5 shadow-[0_24px_60px_rgba(2,6,23,0.38)] backdrop-blur"
    : "min-w-0 rounded-[28px] border border-white/80 bg-white/90 p-5 shadow-[0_18px_45px_rgba(148,163,184,0.16)] backdrop-blur"
)

const metricCardClass = computed(() =>
  isDark.value
    ? "rounded-[24px] border border-slate-800 bg-slate-900/70 p-4 shadow-[0_18px_50px_rgba(2,6,23,0.32)]"
    : "rounded-[24px] border border-white/80 bg-white/90 p-4 shadow-sm"
)

const softPanelClass = computed(() =>
  isDark.value
    ? "rounded-[24px] border border-slate-800 bg-slate-950/65 p-4"
    : "rounded-[24px] border border-slate-200 bg-slate-50 p-4"
)

const chartPanelClass = computed(() =>
  isDark.value
    ? "rounded-[24px] border border-slate-800 bg-slate-950/85 p-4"
    : "rounded-[24px] border border-slate-200 bg-slate-950 p-4"
)

const controlPanelClass = computed(() =>
  isDark.value
    ? "grid gap-4 rounded-[26px] border border-white/10 bg-slate-950/65 p-5 text-slate-100"
    : "grid gap-4 rounded-[26px] border border-slate-200 bg-slate-950 p-5 text-slate-100"
)

const controlInputShellClass = computed(() => "rounded-2xl border border-white/10 bg-white/5 px-4 py-3")
const controlInputClass = computed(() =>
  isDark.value
    ? "mt-1 w-full bg-transparent text-sm text-slate-100 outline-none [color-scheme:dark]"
    : "mt-1 w-full bg-transparent text-sm text-slate-100 outline-none"
)

const primaryButtonClass = computed(() =>
  "rounded-2xl bg-cyan-400 px-4 py-3 text-sm font-medium text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
)
const secondaryButtonClass = computed(() =>
  "rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 transition hover:bg-white/10"
)

const badgeClass = computed(() =>
  isDark.value
    ? "inline-flex items-center gap-2 rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-200"
    : "inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan-700"
)
const pillClass = computed(() =>
  isDark.value
    ? "rounded-full border border-slate-700 bg-slate-950/70 px-3 py-1 text-xs text-slate-300"
    : "rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600"
)
const chipClass = computed(() =>
  isDark.value
    ? "rounded-full border border-slate-700 bg-slate-950/75 px-3 py-1 text-xs text-slate-300"
    : "rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
)
const attentionChipClass = computed(() =>
  "rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-700"
)
const themeToggleClass = computed(() =>
  isDark.value
    ? "rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-400/30 hover:text-white"
    : "rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 transition hover:border-cyan-300 hover:text-slate-900"
)
const toggleAutoClass = computed(() =>
  "rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-100 transition hover:bg-white/10"
)

const heroTitleClass = computed(() =>
  isDark.value ? "text-3xl font-semibold tracking-tight text-slate-100" : "text-3xl font-semibold tracking-tight text-slate-900"
)
const heroTextClass = computed(() =>
  isDark.value ? "max-w-3xl text-sm leading-6 text-slate-300" : "max-w-3xl text-sm leading-6 text-slate-600"
)
const sectionTitleClass = computed(() => (isDark.value ? "text-lg font-semibold text-slate-100" : "text-lg font-semibold text-slate-900"))
const subSectionTitleClass = computed(() => (isDark.value ? "text-sm font-semibold text-slate-100" : "text-sm font-semibold text-slate-900"))
const sectionTextClass = computed(() =>
  isDark.value ? "text-sm text-slate-400" : "text-sm text-slate-500"
)
const bodyTitleClass = computed(() => (isDark.value ? "mt-2 text-lg font-semibold text-slate-100" : "mt-2 text-lg font-semibold text-slate-900"))
const bodyTextClass = computed(() => (isDark.value ? "text-sm font-medium text-slate-100" : "text-sm font-medium text-slate-900"))
const metricValueClass = computed(() => (isDark.value ? "mt-4 text-3xl font-semibold text-slate-100" : "mt-4 text-3xl font-semibold text-slate-900"))
const actionFooterClass = computed(() => (isDark.value ? "mt-4 text-sm font-medium text-slate-100" : "mt-4 text-sm font-medium text-slate-900"))

const emptyStateClass = computed(() =>
  isDark.value
    ? "flex h-full items-center justify-center rounded-[24px] border border-dashed border-slate-700 text-sm text-slate-400"
    : "flex h-full items-center justify-center rounded-[24px] border border-dashed border-slate-200 text-sm text-slate-500"
)
const workerRowClass = computed(() =>
  isDark.value
    ? "flex items-center justify-between gap-3 rounded-[22px] border border-slate-800 bg-slate-950/60 px-4 py-3"
    : "flex items-center justify-between gap-3 rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-3"
)
const operationCardClass = computed(() =>
  isDark.value
    ? "group rounded-[22px] border border-slate-800 bg-slate-950/60 p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
    : "group rounded-[22px] border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
)
const queueRowClass = computed(() =>
  isDark.value
    ? "flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/60 px-3 py-2"
    : "flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2"
)
const noteCardClass = computed(() =>
  isDark.value
    ? "rounded-2xl border border-slate-800 bg-slate-950/60 px-3 py-3 text-xs leading-5 text-slate-400"
    : "rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs leading-5 text-slate-500"
)
const logPanelClass = computed(() =>
  "rounded-[24px] border border-slate-800 bg-slate-950 p-4 text-slate-100"
)
const regionSummaryCardClass = computed(() =>
  "rounded-[22px] border border-slate-200 bg-slate-50 p-4"
)
const mapPanelClass = computed(() =>
  isDark.value
    ? "overflow-hidden rounded-[24px] border border-slate-800 bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.18),transparent_35%),linear-gradient(180deg,#020617,#0f172a)] p-4"
    : "overflow-hidden rounded-[24px] border border-slate-200 bg-[radial-gradient(circle_at_top,rgba(125,211,252,0.26),transparent_34%),linear-gradient(180deg,#f8fafc,#e2e8f0)] p-4"
)
const mapMetaCardClass = computed(() =>
  isDark.value
    ? "rounded-[20px] border border-slate-800 bg-slate-950/60 p-4"
    : "rounded-[20px] border border-slate-200 bg-slate-50 p-4"
)
const tableHeadClass = computed(() =>
  isDark.value
    ? "bg-slate-950 text-left text-[11px] uppercase tracking-[0.18em] text-slate-400"
    : "bg-slate-50 text-left text-[11px] uppercase tracking-[0.18em] text-slate-500"
)
const stateTableWrapClass = computed(() =>
  isDark.value
    ? "overflow-auto rounded-[22px] border border-slate-800 bg-slate-950/40"
    : "overflow-auto rounded-[22px] border border-slate-200 bg-white"
)
const tableRowClass = computed(() =>
  isDark.value ? "border-t border-slate-800" : "border-t border-slate-200"
)
const tablePrimaryTextClass = computed(() => (isDark.value ? "text-sm font-semibold text-slate-100" : "text-sm font-semibold text-slate-900"))
const tablePrimaryCellClass = computed(() => (isDark.value ? "px-4 py-3 font-medium text-slate-100" : "px-4 py-3 font-medium text-slate-900"))
const tablePrimaryRightCellClass = computed(() => (isDark.value ? "px-4 py-3 text-right text-slate-100" : "px-4 py-3 text-right text-slate-900"))
const failureCardClass = computed(() =>
  isDark.value
    ? "rounded-[22px] border border-slate-800 bg-slate-950/60 p-4"
    : "rounded-[22px] border border-slate-200 bg-slate-50 p-4"
)
const reconCardClass = computed(() =>
  isDark.value
    ? "rounded-[22px] border border-slate-800 bg-slate-950/60 p-4"
    : "rounded-[22px] border border-slate-200 bg-slate-50 p-4"
)
const openButtonClass = computed(() =>
  "rounded-full border border-cyan-200 bg-white px-3 py-1 text-xs text-cyan-700 transition hover:bg-cyan-50"
)
const miniInfoCardClass = computed(() =>
  isDark.value
    ? "rounded-2xl border border-slate-800 bg-slate-900/90 px-3 py-2 text-slate-300"
    : "rounded-2xl border border-slate-200 bg-white px-3 py-2 text-slate-600"
)
const subMetricBlueClass = computed(() => "rounded-[22px] border border-blue-200 bg-blue-50 px-4 py-3")
const subMetricVioletClass = computed(() => "rounded-[22px] border border-violet-200 bg-violet-50 px-4 py-3")

const connectivityCards = computed(() => {
  const health = overview.value.health || {}
  const sap = health.sap_login || {}
  const uc = health.uc_login || {}
  return [
    connectionCard("SAP Session", sap.ok, sap.message),
    connectionCard("Unicommerce Session", uc.ok, uc.message),
  ]
})

const topChannel = computed(() => [...channelRows.value].sort((left, right) => (right.cnt || 0) - (left.cnt || 0))[0] || null)
const topRegion = computed(() => [...regionCards.value].sort((left, right) => (right.cnt || 0) - (left.cnt || 0))[0] || null)
const queuePressure = computed(() => (batchValidation.value.fetched_count || 0) + (batchValidation.value.ready_count || 0) + (batchValidation.value.batch_hold_count || 0))
const failurePressure = computed(() => failureRows.value.filter((row) => ["failed", "dead"].includes(String(row.status || "").toLowerCase())).length)
const igstShare = computed(() => {
  if (!totalPostedCount.value) return 0
  return Math.round(((analytics.value.igst?.cnt || 0) / totalPostedCount.value) * 100)
})

const signalCards = computed(() => [
  {
    title: "Top Channel",
    value: topChannel.value?.channel || "No data",
    caption: topChannel.value ? `${num(topChannel.value.cnt)} posted orders` : "No channel activity",
    detail: topChannel.value ? `${money(topChannel.value.tax_total)} tax captured` : "Waiting for posted rows",
    cardClass: isDark.value ? "rounded-[22px] border border-slate-800 bg-slate-950/60 p-4" : "rounded-[22px] border border-slate-200 bg-slate-50 p-4",
    valueClass: isDark.value ? "mt-3 text-xl font-semibold text-slate-100" : "mt-3 text-xl font-semibold text-slate-900",
    detailClass: "mt-2 text-xs font-medium text-cyan-600",
  },
  {
    title: "Interstate Mix",
    value: `${igstShare.value}%`,
    caption: `${num(analytics.value.igst?.cnt)} IGST invoices`,
    detail: `${num(analytics.value.cgst_sgst?.cnt)} intrastate invoices`,
    cardClass: isDark.value ? "rounded-[22px] border border-slate-800 bg-slate-950/60 p-4" : "rounded-[22px] border border-slate-200 bg-slate-50 p-4",
    valueClass: isDark.value ? "mt-3 text-xl font-semibold text-slate-100" : "mt-3 text-xl font-semibold text-slate-900",
    detailClass: "mt-2 text-xs font-medium text-blue-600",
  },
  {
    title: "Queue Pressure",
    value: num(queuePressure.value),
    caption: `${num(batchValidation.value.fetched_count)} fetched / ${num(batchValidation.value.ready_count)} ready`,
    detail: `${num(batchValidation.value.batch_hold_count)} on batch hold`,
    cardClass: isDark.value ? "rounded-[22px] border border-slate-800 bg-slate-950/60 p-4" : "rounded-[22px] border border-slate-200 bg-slate-50 p-4",
    valueClass: isDark.value ? "mt-3 text-xl font-semibold text-slate-100" : "mt-3 text-xl font-semibold text-slate-900",
    detailClass: "mt-2 text-xs font-medium text-amber-600",
  },
  {
    title: "Risk Window",
    value: num(failurePressure.value),
    caption: `${num(reconciliationRows.value.length)} reconciliation gaps`,
    detail: failurePressure.value ? "Immediate attention required" : "No active failure spike",
    cardClass: isDark.value ? "rounded-[22px] border border-slate-800 bg-slate-950/60 p-4" : "rounded-[22px] border border-slate-200 bg-slate-50 p-4",
    valueClass: isDark.value ? "mt-3 text-xl font-semibold text-slate-100" : "mt-3 text-xl font-semibold text-slate-900",
    detailClass: failurePressure.value ? "mt-2 text-xs font-medium text-red-600" : "mt-2 text-xs font-medium text-emerald-600",
  },
])

const kpiCards = computed(() => {
  const counts = overview.value.counts || {}
  const orders = counts.orders || {}
  const creditNotes = counts.credit_notes || {}
  const inventory = counts.inventory || {}
  const totals = analytics.value.total || {}
  const health = overview.value.health || {}
  const failureCount = (orders.failed || 0) + (orders.dead || 0) + (creditNotes.failed || 0) + (creditNotes.dead || 0) + (inventory.Failed || 0) + (inventory.Partial || 0)
  return [
    { title: "Posted Orders", value: num(orders.posted), caption: "Ready queue", detail: num(orders.ready), accent: "text-cyan-600", dotClass: "bg-cyan-500" },
    { title: "Credit Notes", value: num(creditNotes.posted), caption: "Pending", detail: num(creditNotes.pending), accent: "text-violet-600", dotClass: "bg-violet-500" },
    { title: "Blocked Queue", value: num((orders.batch_hold || 0) + (orders.failed || 0) + (orders.dead || 0)), caption: "Batch hold only", detail: num(orders.batch_hold), accent: "text-amber-600", dotClass: "bg-amber-500" },
    { title: "Recon Gaps", value: num(overview.value.recon_summary?.gap_count), caption: "Radar rows", detail: num(reconciliationRows.value.length), accent: "text-orange-600", dotClass: "bg-orange-500" },
    { title: "SAP Tax", value: money(totals.tax_total), caption: "Invoice count", detail: num(totals.cnt), accent: "text-emerald-600", dotClass: "bg-emerald-500" },
    { title: "Health", value: health.sap_login?.ok && health.uc_login?.ok ? "Live" : "Attention", caption: "Active failures", detail: num(failureCount), accent: failureCount ? "text-red-600" : "text-emerald-600", dotClass: failureCount ? "bg-red-500" : "bg-emerald-500" },
  ]
})

const queueCards = computed(() => [
  { label: "Fetched", value: num(batchValidation.value.fetched_count), valueClass: isDark.value ? "text-sm font-semibold text-slate-100" : "text-sm font-semibold text-slate-900" },
  { label: "Ready", value: num(batchValidation.value.ready_count), valueClass: isDark.value ? "text-sm font-semibold text-slate-100" : "text-sm font-semibold text-slate-900" },
  { label: "Batch Hold", value: num(batchValidation.value.batch_hold_count), valueClass: "text-sm font-semibold text-amber-700" },
])

const timelineHasData = computed(() => timelineRows.value.some((row) => row.fetched || row.ready || row.posted || row.blocked))
const taxSplitHasData = computed(() => (analytics.value.igst?.cnt || 0) + (analytics.value.cgst_sgst?.cnt || 0) > 0)
const channelHasData = computed(() => channelRows.value.length > 0)
const dailyTrendHasData = computed(() => dailyRows.value.some((row) => row.cnt || row.tax_total))
const transferHasData = computed(() => transferDailyRows.value.some((row) => row.total || row.posted || row.failed || row.pending))
const monthlyHasData = computed(() => monthlyRows.value.length > 0)

const chartLegendColor = computed(() => (isDark.value ? "#cbd5e1" : "#475569"))
const chartGridColor = computed(() => (isDark.value ? "rgba(148,163,184,0.10)" : "rgba(148,163,184,0.14)"))
const chartTickColor = computed(() => (isDark.value ? "#94a3b8" : "#64748b"))
const chartYColor = computed(() => (isDark.value ? "#cbd5e1" : "#334155"))

const timelineChartData = computed(() => ({
  labels: timelineRows.value.map((row) => row.day),
  datasets: [
    { label: "Fetched", data: timelineRows.value.map((row) => row.fetched), backgroundColor: "rgba(148,163,184,0.78)", borderRadius: 8 },
    { label: "Ready", data: timelineRows.value.map((row) => row.ready), backgroundColor: "rgba(59,130,246,0.82)", borderRadius: 8 },
    { label: "Posted", data: timelineRows.value.map((row) => row.posted), backgroundColor: "rgba(16,185,129,0.84)", borderRadius: 8 },
    { label: "Blocked", data: timelineRows.value.map((row) => row.blocked), backgroundColor: "rgba(245,158,11,0.88)", borderRadius: 8 },
  ],
}))

const timelineChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: chartLegendColor.value } },
    tooltip: { intersect: false, mode: "index" },
  },
  scales: {
    x: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value } },
    y: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value }, beginAtZero: true },
  },
}))

const taxSplitChartData = computed(() => ({
  labels: ["IGST", "CGST+SGST"],
  datasets: [
    {
      data: [analytics.value.igst?.cnt || 0, analytics.value.cgst_sgst?.cnt || 0],
      backgroundColor: ["rgba(59,130,246,0.88)", "rgba(139,92,246,0.88)"],
      borderColor: ["rgba(59,130,246,1)", "rgba(139,92,246,1)"],
      borderWidth: 1,
    },
  ],
}))

const taxSplitChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: "bottom", labels: { color: chartLegendColor.value } } },
  cutout: "62%",
}))

const channelChartData = computed(() => ({
  labels: channelRows.value.slice(0, 7).map((row) => row.channel),
  datasets: [
    { label: "Orders Posted", data: channelRows.value.slice(0, 7).map((row) => row.cnt), backgroundColor: "rgba(34,197,94,0.78)", borderRadius: 10 },
    { label: "Recon Gaps", data: channelRows.value.slice(0, 7).map((row) => row.gap_count), backgroundColor: "rgba(251,191,36,0.82)", borderRadius: 10 },
  ],
}))

const channelChartOptions = computed(() => ({
  indexAxis: "y",
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: chartLegendColor.value } } },
  scales: {
    x: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value }, beginAtZero: true },
    y: { ticks: { color: chartYColor.value }, grid: { display: false } },
  },
}))

const dailyTrendChartData = computed(() => ({
  labels: dailyRows.value.map((row) => (row.day ? String(row.day).slice(5) : "")),
  datasets: [
    {
      type: "bar",
      label: "Orders",
      data: dailyRows.value.map((row) => row.cnt || 0),
      backgroundColor: "rgba(14,165,233,0.42)",
      borderRadius: 8,
      yAxisID: "y",
    },
    {
      type: "line",
      label: "Tax",
      data: dailyRows.value.map((row) => row.tax_total || 0),
      borderColor: "rgba(16,185,129,0.96)",
      backgroundColor: "rgba(16,185,129,0.14)",
      fill: true,
      tension: 0.32,
      pointRadius: 3,
      pointBackgroundColor: "rgba(16,185,129,1)",
      yAxisID: "y1",
    },
  ],
}))

const dailyTrendChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: { legend: { labels: { color: chartLegendColor.value } } },
  scales: {
    x: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value } },
    y: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value }, beginAtZero: true },
    y1: {
      position: "right",
      ticks: { color: chartTickColor.value, callback: (value) => `Rs ${Number(value).toLocaleString("en-IN")}` },
      grid: { display: false },
      beginAtZero: true,
    },
  },
}))

const transferChartData = computed(() => ({
  labels: transferDailyRows.value.map((row) => (row.day ? String(row.day).slice(5) : "")),
  datasets: [
    {
      label: "Posted",
      data: transferDailyRows.value.map((row) => row.posted || 0),
      backgroundColor: "rgba(16,185,129,0.82)",
      borderRadius: 8,
    },
    {
      label: "Pending",
      data: transferDailyRows.value.map((row) => row.pending || 0),
      backgroundColor: "rgba(59,130,246,0.78)",
      borderRadius: 8,
    },
    {
      label: "Failed",
      data: transferDailyRows.value.map((row) => row.failed || 0),
      backgroundColor: "rgba(245,158,11,0.84)",
      borderRadius: 8,
    },
  ],
}))

const transferChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: chartLegendColor.value } } },
  scales: {
    x: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value } },
    y: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value }, beginAtZero: true },
  },
}))

const monthlyChartRows = computed(() => {
  const grouped = new Map()
  for (const row of monthlyRows.value) {
    const key = row.month
    if (!grouped.has(key)) {
      grouped.set(key, {
        month: row.month,
        month_label: row.month_label,
        uc_taxable_total: 0,
        sap_taxable_total: 0,
        total_tax_diff: 0,
      })
    }
    const target = grouped.get(key)
    target.uc_taxable_total += Number(row.uc_taxable_total || 0)
    target.sap_taxable_total += Number(row.sap_taxable_total || 0)
    target.total_tax_diff += Math.abs(Number(row.total_tax_diff || 0))
  }
  return Array.from(grouped.values()).sort((left, right) => String(left.month).localeCompare(String(right.month)))
})

const monthlyChartData = computed(() => ({
  labels: monthlyChartRows.value.map((row) => row.month_label),
  datasets: [
    {
      label: "UC Taxable",
      data: monthlyChartRows.value.map((row) => row.uc_taxable_total),
      backgroundColor: "rgba(14,165,233,0.74)",
      borderRadius: 8,
    },
    {
      label: "SAP Taxable",
      data: monthlyChartRows.value.map((row) => row.sap_taxable_total),
      backgroundColor: "rgba(16,185,129,0.82)",
      borderRadius: 8,
    },
    {
      label: "Abs Tax Drift",
      data: monthlyChartRows.value.map((row) => row.total_tax_diff),
      backgroundColor: "rgba(245,158,11,0.82)",
      borderRadius: 8,
    },
  ],
}))

const monthlyChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { labels: { color: chartLegendColor.value } } },
  scales: {
    x: { ticks: { color: chartTickColor.value }, grid: { color: chartGridColor.value } },
    y: {
      ticks: { color: chartTickColor.value, callback: (value) => `Rs ${Number(value).toLocaleString("en-IN")}` },
      grid: { color: chartGridColor.value },
      beginAtZero: true,
    },
  },
}))

const regionCards = computed(() => {
  const rows = analytics.value.by_region || []
  const mapped = new Map(rows.map((row) => [row.region, row]))
  return REGION_ORDER.filter((region) => mapped.has(region)).map((region) => mapped.get(region))
})

const regionMapNodes = computed(() => {
  const rows = new Map(regionCards.value.map((row) => [row.region, row]))
  const maxCount = Math.max(...regionCards.value.map((row) => row.cnt || 0), 1)
  return REGION_ORDER.map((region) => {
    const source = rows.get(region) || { region, cnt: 0, tax_total: 0, states: [] }
    const ratio = (source.cnt || 0) / maxCount
    const tone = 0.22 + ratio * 0.55
    return {
      region,
      x: REGION_COORDINATES[region].x,
      y: REGION_COORDINATES[region].y,
      radius: 7 + ratio * 7,
      fill: isDark.value ? `rgba(34,211,238,${Math.max(0.25, tone)})` : `rgba(14,165,233,${Math.max(0.24, tone)})`,
      ring: isDark.value ? "rgba(56,189,248,0.4)" : "rgba(59,130,246,0.26)",
      stroke: isDark.value ? "rgba(103,232,249,0.75)" : "rgba(37,99,235,0.45)",
      countLabel: num(source.cnt),
      taxLabel: money(source.tax_total),
      statesLabel: source.states?.slice(0, 4).join(", ") || "No states mapped",
      cnt: source.cnt || 0,
    }
  })
})

const workerRows = computed(() => {
  const lastRuns = overview.value.last_runs || {}
  return Object.entries(lastRuns).map(([name, info]) => ({
    name,
    label: shortWorker(name),
    at: info?.at ? shortTime(info.at) : "Never",
    status: info?.status || "never",
    badgeClass:
      info?.status === "Complete"
        ? "rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700"
        : "rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700",
  }))
})

function createDashboardState() {
  return {
    overview: {
      health: { sap_login: { ok: false, message: "" }, uc_login: { ok: false, message: "" } },
      counts: { orders: {}, credit_notes: {}, inventory: {} },
      last_runs: {},
      recon_summary: { gap_count: 0 },
      generated_at: "",
    },
    analytics: {
      by_channel: [],
      by_state: [],
      by_region: [],
      daily: [],
      igst: { cnt: 0, tax_total: 0 },
      cgst_sgst: { cnt: 0, tax_total: 0 },
      total: { cnt: 0, tax_total: 0 },
      cn_total: 0,
    },
    activity: { jobs: [], errors: [] },
    failures: { rows: [] },
    batch_validation: { batch_hold_count: 0, ready_count: 0, fetched_count: 0, batch_hold_orders: [] },
    reconciliation: { invoice_gaps: [] },
    inventory_parity: { item_count: 0, matched_count: 0, mismatch_count: 0, total_delta_qty: 0, rows: [], message: "" },
    transfers: { total_to_ec_fg: 0, po_created: 0, approved: 0, grn_completed: 0, posted_to_unicommerce: 0, failed: 0, partial: 0, pending: 0, rows: [], daily: [] },
    monthly_reconciliation: { rows: [], top_drift_rows: [], months: [] },
    timeline: [],
    generated_at: "",
  }
}

function connectionCard(label, ok, message) {
  return {
    label,
    status: ok ? "Connected" : "Needs attention",
    badge: ok ? "Live" : "Down",
    message: message || (ok ? "Session check passed." : "Connection status unavailable."),
    cardClass: isDark.value ? "rounded-[22px] border border-slate-800 bg-slate-900/90 p-4" : "rounded-[22px] border border-white/10 bg-white/10 p-4",
    badgeClass: ok
      ? "rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700"
      : "rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-700",
  }
}

function getStoredTheme() {
  if (typeof window === "undefined") return "light"
  const stored = window.localStorage?.getItem(THEME_STORAGE_KEY)
  if (stored === "light" || stored === "dark") return stored
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light"
}

function getStoredAutoRefresh() {
  if (typeof window === "undefined") return true
  const stored = window.localStorage?.getItem(AUTO_REFRESH_STORAGE_KEY)
  return stored === null ? true : stored === "true"
}

function toggleTheme() {
  themeMode.value = isDark.value ? "light" : "dark"
}

function toggleAutoRefresh() {
  autoRefreshEnabled.value = !autoRefreshEnabled.value
}

function syncAutoRefresh() {
  if (refreshHandle) {
    window.clearInterval(refreshHandle)
    refreshHandle = null
  }
  if (autoRefreshEnabled.value && typeof window !== "undefined") {
    refreshHandle = window.setInterval(() => {
      loadDashboard({ silent: true })
    }, REFRESH_INTERVAL_MS)
  }
}

function frappeCall(method, args = {}) {
  return new Promise((resolve, reject) => {
    const frappeObj =
      (typeof frappe !== "undefined" && frappe && frappe.call && frappe) ||
      (typeof window !== "undefined" && window.frappe && window.frappe.call && window.frappe) ||
      null

    if (frappeObj) {
      frappeObj.call({
        method,
        args,
        callback: (response) => {
          if (response && response.message !== undefined) {
            resolve(response.message)
          } else if (response && response.exc) {
            reject(new Error(response.exc))
          } else {
            resolve(response)
          }
        },
        error: (response) => {
          const message =
            response?.message ||
            response?.exc ||
            response?.responseJSON?.exc ||
            response?.responseJSON?.message ||
            "Request failed"
          reject(new Error(message))
        },
      })
      return
    }

    const csrfToken = window?.csrf_token || window?.boot?.csrf_token || null
    frappeRequest({
      method: "POST",
      url: method,
      params: args,
      headers: csrfToken ? { "X-Frappe-CSRF-Token": csrfToken } : undefined,
    })
      .then((response) => resolve(response))
      .catch((error) => reject(new Error(error?.message || "Request failed")))
  })
}

async function loadDashboard({ silent = false } = {}) {
  if (loading.dashboard && silent) return
  loading.dashboard = true
  try {
    dashboard.value = {
      ...createDashboardState(),
      ...(await frappeCall(`${OPS_API}.ops_dashboard_data`, {
        start_date: filters.startDate,
        end_date: filters.endDate,
        hours: 24,
        timeline_days: 14,
      })),
    }
  } catch (error) {
    appendLog("dashboard", error)
  } finally {
    loading.dashboard = false
  }
}

async function runWorker(action) {
  loading.actions[action.worker] = true
  try {
    const result = await frappeCall(`${OPS_API}.ops_run_worker`, { worker: action.worker })
    appendLog(action.label, result)
    await loadDashboard()
  } catch (error) {
    appendLog(action.label, error)
  } finally {
    loading.actions[action.worker] = false
  }
}

function appendLog(label, value) {
  const message = formatLogValue(value)
  actionLog.value = `[${new Date().toLocaleString()}] ${label}\n${message}\n\n${actionLog.value}`.trim()
}

function formatLogValue(value) {
  if (value instanceof Error) return value.message
  if (typeof value === "string") return value
  if (value && typeof value === "object") {
    if (value.ok === false && value.error) return `${value.error}\n${JSON.stringify(value, null, 2)}`
    if (value.ok === true && value.result !== undefined) return JSON.stringify(value.result, null, 2)
  }
  return JSON.stringify(value, null, 2)
}

function setMonthRange(offset) {
  filters.startDate = monthStart(offset)
  filters.endDate = monthEnd(offset)
  loadDashboard()
}

function setRollingRange(days) {
  filters.startDate = rollingStart(days)
  filters.endDate = rollingEnd()
  loadDashboard()
}

function monthStart(offset) {
  const base = new Date()
  const date = new Date(base.getFullYear(), base.getMonth() + offset, 1)
  return isoDate(date)
}

function monthEnd(offset) {
  const base = new Date()
  const date = new Date(base.getFullYear(), base.getMonth() + offset + 1, 0)
  return isoDate(date)
}

function rollingStart(days) {
  const base = new Date()
  const date = new Date(base.getFullYear(), base.getMonth(), base.getDate() - Math.max(days - 1, 0))
  return isoDate(date)
}

function rollingEnd() {
  return isoDate(new Date())
}

function isoDate(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
}

function num(value) {
  return Number(value || 0).toLocaleString("en-IN")
}

function money(value) {
  return `Rs ${Number(value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function shortTime(value) {
  if (!value) return "-"
  return String(value).replace("T", " ").slice(0, 16)
}

function shortWorker(path) {
  return String(path || "")
    .split(".")
    .pop()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
}

function regionStyle(region) {
  const max = Math.max(...regionCards.value.map((row) => row.cnt || 0), 1)
  const intensity = Math.max(0.18, (region.cnt || 0) / max)
  return {
    background: `linear-gradient(135deg, rgba(255,255,255,0.94), rgba(224,242,254,${0.14 + intensity * 0.22}))`,
    borderColor: `rgba(186,230,253,${0.3 + intensity * 0.2})`,
  }
}

function failureBadgeClass(status) {
  const normalized = String(status || "").toLowerCase()
  if (normalized === "dead" || normalized === "failed") return "bg-red-100 text-red-700"
  if (normalized === "partial" || normalized === "batch_hold") return "bg-amber-100 text-amber-700"
  return "bg-slate-100 text-slate-700"
}

function recordHref(gap) {
  const routeMap = {
    "UC Order Staging": "uc-order-staging",
    "UC Credit Note Staging": "uc-credit-note-staging",
    "Unicommerce Orders": "unicommerce-orders",
  }
  const route = routeMap[gap.record_doctype] || String(gap.record_doctype || "").toLowerCase().replace(/ /g, "-")
  return `/app/${route}/${encodeURIComponent(gap.record_name)}`
}

watch(themeMode, (value) => {
  if (typeof window !== "undefined") {
    window.localStorage?.setItem(THEME_STORAGE_KEY, value)
  }
})

watch(autoRefreshEnabled, (value) => {
  if (typeof window !== "undefined") {
    window.localStorage?.setItem(AUTO_REFRESH_STORAGE_KEY, String(value))
  }
  syncAutoRefresh()
})

onMounted(() => {
  syncAutoRefresh()
  loadDashboard()
})

onUnmounted(() => {
  if (refreshHandle && typeof window !== "undefined") {
    window.clearInterval(refreshHandle)
  }
})
</script>
