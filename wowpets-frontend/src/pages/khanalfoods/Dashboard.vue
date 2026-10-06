<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">KhanalFoods Dashboard</h1>

    <!-- Stat cards — accurate counts from server -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
      <DashCard label="Draft POs"              :count="stats.draftPO"         color="gray"   to="/khanalfoods/purchase-orders" />
      <DashCard label="PO Pending Approval"    :count="stats.pendingPO"       color="yellow" to="/khanalfoods/purchase-orders" />
      <DashCard label="Draft FBA Transfers"    :count="stats.draftFBA"        color="gray"   to="/khanalfoods/orders" />
      <DashCard label="FBA Pending Approval"   :count="stats.pendingFBA"      color="yellow" to="/khanalfoods/orders" />
      <DashCard label="Draft Work Orders"      :count="stats.draftWO"         color="gray"   to="/khanalfoods/work-orders" />
      <DashCard label="WO Pending Approval"    :count="stats.pendingWO"       color="yellow" to="/khanalfoods/work-orders" />
      <DashCard label="Draft Dispatch Orders"  :count="stats.draftDispatch"   color="gray"   to="/khanalfoods/dispatch-orders" />
      <DashCard label="Draft ShipHero Transfers" :count="stats.draftShiphero" color="gray"   to="/khanalfoods/shiphero-transfers" />
      <DashCard label="Open Tickets"           :count="stats.openTickets"     color="red"    to="/khanalfoods/tickets" />
    </div>

    <!-- Recent lists -->
    <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      <RecentListCard
        title="Recent Purchase Orders"
        view-all-route="/khanalfoods/purchase-orders"
        :items="recentPOs"
        :get-row-link="(po) => `/khanalfoods/purchase-orders/${po.name}`"
        :primary-label="(po) => po.purchase_order_name || po.name"
        :secondary-label="(po) => po.supplier_name || ''"
        :status="(po) => po.status"
        empty-message="No purchase orders yet"
      />
      <RecentListCard
        title="Recent FBA Transfers"
        view-all-route="/khanalfoods/orders"
        :items="recentOrders"
        :get-row-link="(o) => `/khanalfoods/orders/${o.name}`"
        :primary-label="(o) => o.fba_transfer_name || o.name"
        :secondary-label="(o) => o.sap_doc_entry ? `SAP ${o.sap_doc_entry}` : ''"
        :status="(o) => o.status"
        empty-message="No FBA transfers yet"
      />
      <RecentListCard
        title="Recent Dispatch Orders"
        view-all-route="/khanalfoods/dispatch-orders"
        :items="recentDispatch"
        :get-row-link="(d) => `/khanalfoods/dispatch-orders/${d.name}`"
        :primary-label="(d) => d.dispatch_order_name || d.name"
        :secondary-label="(d) => d.card_name || d.card_code || ''"
        :status="(d) => d.status"
        empty-message="No dispatch orders yet"
      />
      <RecentListCard
        title="Recent Work Orders"
        view-all-route="/khanalfoods/work-orders"
        :items="recentWOs"
        :get-row-link="(wo) => `/khanalfoods/work-orders/${wo.name}`"
        :primary-label="(wo) => wo.work_order_name || wo.name"
        :secondary-label="(wo) => wo.finished_item_code || ''"
        :status="(wo) => wo.status"
        empty-message="No work orders yet"
      />
      <RecentListCard
        title="Recent ShipHero Transfers"
        view-all-route="/khanalfoods/shiphero-transfers"
        :items="recentTransfers"
        :get-row-link="(t) => `/khanalfoods/shiphero-transfers/${t.name}`"
        :primary-label="(t) => t.inventory_transfer_name || t.name"
        :secondary-label="(t) => t.from_warehouse && t.to_warehouse ? `${t.from_warehouse} → ${t.to_warehouse}` : ''"
        :status="(t) => t.status"
        empty-message="No ShipHero transfers yet"
      />
      <RecentListCard
        title="Recent Returns"
        view-all-route="/khanalfoods/returns"
        :items="recentReturns"
        :get-row-link="() => '/khanalfoods/returns'"
        :primary-label="(r) => r.name"
        :secondary-label="(r) => r.posting_date || r.return_type || ''"
        :status="(r) => r.status"
        empty-message="No returns yet"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchPurchaseOrders } from '@/core/api/purchaseOrders.js'
import { fetchWorkOrders } from '@/core/api/workOrders.js'
import { fetchShipheroTransfers } from '@/core/api/shipheroTransfers.js'
import { fetchOrders } from '@/core/api/orders.js'
import { fetchDispatchOrders } from '@/core/api/dispatchOrders.js'
import { fetchReturns } from '@/core/api/returns.js'
import { fetchTicketSummary } from '@/core/api/tickets.js'
import DashCard from './DashCard.vue'
import RecentListCard from '@/components/common/RecentListCard.vue'

const stats = ref({
  draftPO: null, pendingPO: null,
  draftFBA: null, pendingFBA: null,
  draftWO: null, pendingWO: null,
  draftDispatch: null, draftShiphero: null, openTickets: null,
})
const recentPOs = ref([])
const recentWOs = ref([])
const recentTransfers = ref([])
const recentOrders = ref([])
const recentDispatch = ref([])
const recentReturns = ref([])

onMounted(async () => {
  try {
    const [
      draftPORes, pendingPORes,
      draftFBARes, pendingFBARes,
      draftWORes, pendingWORes,
      draftDispatchRes, draftShipheroRes,
      ticketRes,
      poList, woList, transferList, orderList, dispatchList, returnList,
    ] = await Promise.all([
      // Accurate stat counts (page_size: 1 — only need total)
      fetchPurchaseOrders({ status: 'Draft', page_size: 1 }),
      fetchPurchaseOrders({ status: 'Pending Approval', page_size: 1 }),
      fetchOrders({ status: 'Draft', page_size: 1 }),
      fetchOrders({ status: 'Pending Approval', page_size: 1 }),
      fetchWorkOrders({ status: 'Draft', page_size: 1 }),
      fetchWorkOrders({ status: 'Pending Approval', page_size: 1 }),
      fetchDispatchOrders({ status: 'Draft', page_size: 1 }),
      fetchShipheroTransfers({ status: 'Draft', page_size: 1 }),
      fetchTicketSummary({ status: 'Open', page_size: 1 }),
      // Recent lists
      fetchPurchaseOrders({ page_size: 5 }),
      fetchWorkOrders({ page_size: 5 }),
      fetchShipheroTransfers({ page_size: 5 }),
      fetchOrders({ page_size: 5 }),
      fetchDispatchOrders({ page_size: 5 }),
      fetchReturns({ page_size: 5 }),
    ])

    stats.value.draftPO       = draftPORes.total ?? 0
    stats.value.pendingPO     = pendingPORes.total ?? 0
    stats.value.draftFBA      = draftFBARes.total ?? 0
    stats.value.pendingFBA    = pendingFBARes.total ?? 0
    stats.value.draftWO       = draftWORes.total ?? 0
    stats.value.pendingWO     = pendingWORes.total ?? 0
    stats.value.draftDispatch = draftDispatchRes.total ?? 0
    stats.value.draftShiphero = draftShipheroRes.total ?? 0
    stats.value.openTickets   = ticketRes.total ?? 0

    recentPOs.value       = poList.data || []
    recentWOs.value       = woList.data || []
    recentTransfers.value = transferList.data || []
    recentOrders.value    = orderList.data || []
    recentDispatch.value  = dispatchList.data || []
    recentReturns.value   = returnList.data || []
  } catch { /* handled by interceptor */ }
})
</script>
