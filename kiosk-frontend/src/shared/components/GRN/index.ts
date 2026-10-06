/**
 * Shared GRN Components
 * Reusable components for GRN functionality across all plants
 * 
 * These components provide a consistent UI/UX for GRN operations
 * across Krishnagiri, Malur, Mahadevpura, Nandi Hills, and Champavath plants.
 */

// Export all GRN components
export { default as GRNFormHeader } from './GRNFormHeader.vue'
export { default as GRNSearchSection } from './GRNSearchSection.vue'
export { default as GRNItemsTable } from './GRNItemsTable.vue'
export { default as GRNItemsTableRow } from './GRNItemsTableRow.vue'
export { default as GRNFormFooter } from './GRNFormFooter.vue'
export { default as GRNSummary } from './GRNSummary.vue'
export { default as GRNStatusBadge } from './GRNStatusBadge.vue'
export { default as CancelGRNModal } from './CancelGRNModal.vue'

// Export types
export type { TableColumn } from './GRNItemsTable.vue'

/**
 * Usage Example:
 * 
 * import {
 *   GRNFormHeader,
 *   GRNSearchSection,
 *   GRNItemsTable,
 *   GRNFormFooter,
 *   GRNSummary,
 *   GRNStatusBadge
 * } from '@/shared/components/GRN'
 * 
 * // In your plant-specific CreateGRNForm.vue:
 * <GRNFormHeader
 *   title="Create GRN"
 *   :po-number="selectedPO?.DocNum"
 *   :vendor-name="selectedPO?.CardName"
 *   @back="handleBack"
 * />
 * 
 * <GRNSearchSection
 *   v-model:from-date="fromDate"
 *   v-model:to-date="toDate"
 *   v-model:bp-search="bpSearch"
 *   @fetch="loadPurchaseOrders"
 * />
 * 
 * <GRNItemsTable
 *   :items="lineItems"
 *   :columns="tableColumns"
 *   @update-item="handleItemUpdate"
 * />
 * 
 * <GRNFormFooter
 *   :can-submit="isValid"
 *   :total-amount="totalAmount"
 *   @submit="handleSubmit"
 * />
 */

