<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">Real Aquatics Warehouse Dashboard</h1>

    <!-- Stat cards — accurate counts from server -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
      <DashCard label="POs to Accept"          :count="stats.pendingPO"         color="yellow"  to="/warehouse/purchase-orders" />
      <DashCard label="POs Accepted"           :count="stats.acceptedPO"        color="blue"    to="/warehouse/purchase-orders" />
      <DashCard label="WOs to Start"           :count="stats.pendingWO"         color="yellow"  to="/warehouse/work-orders" />
      <DashCard label="WOs In Progress"        :count="stats.inProgressWO"      color="purple"  to="/warehouse/work-orders" />
      <DashCard label="Dispatch to Prepare"    :count="stats.acceptedDispatch"  color="blue"    to="/warehouse/dispatch-orders" />
      <DashCard label="FBA to Accept"          :count="stats.approvedFBA"       color="yellow"  to="/warehouse/orders" />
      <DashCard label="FBA Accepted"           :count="stats.acceptedFBA"       color="blue"    to="/warehouse/orders" />
      <DashCard label="Open Tickets"           :count="stats.openTickets"       color="red"     to="/warehouse/tickets" />
    </div>

    <!-- Recent lists -->
    <div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      <RecentListCard
        title="Pending Purchase Orders"
        view-all-route="/warehouse/purchase-orders"
        :items="recentPOs"
        :get-row-link="(po) => `/warehouse/purchase-orders/${po.name}`"
        :primary-label="(po) => po.purchase_order_name || po.name"
        :secondary-label="(po) => po.supplier_name || ''"
        :status="(po) => po.status"
        empty-message="No pending POs"
      />
      <RecentListCard
        title="Pending FBA Transfers"
        view-all-route="/warehouse/orders"
        :items="recentOrders"
        :get-row-link="(o) => `/warehouse/orders/${o.name}`"
        :primary-label="(o) => o.fba_transfer_name || o.name"
        :secondary-label="(o) => o.sap_doc_entry ? `SAP ${o.sap_doc_entry}` : ''"
        :status="(o) => o.status"
        empty-message="No pending FBA transfers"
      />
      <RecentListCard
        title="Dispatch Orders to Process"
        view-all-route="/warehouse/dispatch-orders"
        :items="recentDispatch"
        :get-row-link="(d) => `/warehouse/dispatch-orders/${d.name}`"
        :primary-label="(d) => d.dispatch_order_name || d.name"
        :secondary-label="(d) => d.card_name || d.card_code || ''"
        :status="(d) => d.status"
        empty-message="No dispatch orders to process"
      />
      <RecentListCard
        title="Pending Work Orders"
        view-all-route="/warehouse/work-orders"
        :items="recentWOs"
        :get-row-link="(wo) => `/warehouse/work-orders/${wo.name}`"
        :primary-label="(wo) => wo.work_order_name || wo.name"
        :secondary-label="(wo) => wo.finished_item_code || ''"
        :status="(wo) => wo.status"
        empty-message="No pending WOs"
      />
      <RecentListCard
        title="Recent Returns"
        view-all-route="/warehouse/returns"
        :items="recentReturns"
        :get-row-link="() => '/warehouse/returns'"
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
import { fetchOrders } from '@/core/api/orders.js'
import { fetchDispatchOrders } from '@/core/api/dispatchOrders.js'
import { fetchReturns } from '@/core/api/returns.js'
import { fetchTicketSummary } from '@/core/api/tickets.js'
import DashCard from '@/pages/khanalfoods/DashCard.vue'
import RecentListCard from '@/components/common/RecentListCard.vue'

const stats = ref({
  pendingPO: null, acceptedPO: null,
  pendingWO: null, inProgressWO: null,
  acceptedDispatch: null,
  approvedFBA: null, acceptedFBA: null,
  openTickets: null,
})
const recentPOs = ref([])
const recentWOs = ref([])
const recentOrders = ref([])
const recentDispatch = ref([])
const recentReturns = ref([])

onMounted(async () => {
  try {
    const [
      pendingPORes, acceptedPORes,
      pendingWORes, inProgressWORes,
      acceptedDispatchRes,
      approvedFBARes, acceptedFBARes,
      ticketRes,
      poList, woList, orderList, dispatchList, returnList,
    ] = await Promise.all([
      // Accurate stat counts
      fetchPurchaseOrders({ status: 'Approved', page_size: 1 }),
      fetchPurchaseOrders({ status: 'Accepted', page_size: 1 }),
      fetchWorkOrders({ status: 'Approved', page_size: 1 }),
      fetchWorkOrders({ status: 'In Progress', page_size: 1 }),
      fetchDispatchOrders({ status: 'Accepted', page_size: 1 }),
      fetchOrders({ status: 'Approved', page_size: 1 }),
      fetchOrders({ status: 'Accepted', page_size: 1 }),
      fetchTicketSummary({ status: 'Open', page_size: 1 }),
      // Recent lists — show actionable statuses for warehouse
      fetchPurchaseOrders({ status: 'Approved', page_size: 5 }),
      fetchWorkOrders({ status: 'Approved', page_size: 5 }),
      fetchOrders({ status: 'Approved', page_size: 5 }),
      fetchDispatchOrders({ status: 'Accepted', page_size: 5 }),
      fetchReturns({ page_size: 5 }),
    ])

    stats.value.pendingPO        = pendingPORes.total ?? 0
    stats.value.acceptedPO       = acceptedPORes.total ?? 0
    stats.value.pendingWO        = pendingWORes.total ?? 0
    stats.value.inProgressWO     = inProgressWORes.total ?? 0
    stats.value.acceptedDispatch = acceptedDispatchRes.total ?? 0
    stats.value.approvedFBA      = approvedFBARes.total ?? 0
    stats.value.acceptedFBA      = acceptedFBARes.total ?? 0
    stats.value.openTickets      = ticketRes.total ?? 0

    recentPOs.value       = poList.data || []
    recentWOs.value       = woList.data || []
    recentOrders.value    = orderList.data || []
    recentDispatch.value  = dispatchList.data || []
    recentReturns.value   = returnList.data || []
  } catch { /* handled by interceptor */ }
})
</script>
