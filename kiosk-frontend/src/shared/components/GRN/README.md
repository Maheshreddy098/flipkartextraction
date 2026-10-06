# Shared GRN Components 📦

Reusable Vue components for GRN (Goods Receipt Note) functionality across all plants.

## Components

### 1. **GRNFormHeader.vue**
Page header with navigation and PO information.

**Props:**
- `title` - Page title
- `subtitle` - Optional subtitle
- `poNumber` - Purchase order number
- `vendorName` - Vendor/supplier name
- `showBackButton` - Show/hide back button
- `showHelpButton` - Show/hide help button

**Events:**
- `@back` - Back button clicked
- `@show-help` - Help button clicked

**Slots:**
- `actions` - Custom action buttons

---

### 2. **GRNSearchSection.vue**
Search and filter controls for fetching purchase orders.

**Props:**
- `fetchAll` - Fetch all POs (no date filter)
- `fromDate` - Start date
- `toDate` - End date
- `bpSearch` - Business partner search term
- `loading` - Loading state
- `resultsCount` - Number of results found
- `quickDateOptions` - Quick date range options

**Events:**
- `@update:fetchAll` - Fetch all checkbox changed
- `@update:fromDate` - From date changed
- `@update:toDate` - To date changed
- `@update:bpSearch` - BP search changed
- `@quick-date` - Quick date button clicked
- `@fetch` - Fetch button clicked

---

### 3. **GRNItemsTable.vue**
Table container for displaying GRN line items.

**Props:**
- `title` - Table title
- `items` - Array of items
- `columns` - Column definitions
- `loading` - Loading state
- `emptyText` - Empty state message
- `showActions` - Show/hide actions column

**Events:**
- `@update-item` - Item field updated
- `@delete-item` - Item delete requested

**Slots:**
- `bulk-actions` - Bulk action buttons
- `filters` - Filter controls
- `footer` - Table footer content

---

### 4. **GRNItemsTableRow.vue**
Individual table row with editable fields.

**Props:**
- `item` - Item data
- `index` - Row index
- `columns` - Column definitions
- `showActions` - Show/hide actions
- `editableFields` - Array of editable field names
- `highlightErrors` - Highlight error/warning fields

**Events:**
- `@update` - Field value updated
- `@delete` - Delete button clicked
- `@blur` - Input field blurred

**Slots:**
- `cell-{key}` - Custom cell content for column
- `actions` - Custom actions

---

### 5. **GRNFormFooter.vue**
Sticky footer with totals and action buttons.

**Props:**
- `itemsCount` - Number of items
- `totalQuantity` - Total quantity
- `totalAmount` - Total amount
- `canSubmit` - Enable/disable submit
- `canSaveDraft` - Enable/disable save draft
- `submitting` - Submitting state
- `showCancelButton` - Show/hide cancel
- `showSaveDraftButton` - Show/hide save draft
- `errorMessage` - Error message
- `warningMessage` - Warning message
- `successMessage` - Success message

**Events:**
- `@submit` - Submit button clicked
- `@cancel` - Cancel button clicked
- `@save-draft` - Save draft clicked

**Slots:**
- `stats` - Custom statistics
- `actions` - Custom action buttons

---

### 6. **GRNSummary.vue**
Progress tracker with statistics.

**Props:**
- `title` - Summary title
- `completedItems` - Completed count
- `partialItems` - Partial count
- `pendingItems` - Pending count
- `totalItems` - Total count
- `customStats` - Custom stat objects

**Slots:**
- `additional-info` - Additional info below stats

---

### 7. **GRNStatusBadge.vue**
Colored status badge with icon.

**Props:**
- `status` - Status type: 'open' | 'closed' | 'partial' | 'pending' | 'completed' | 'error' | 'warning' | 'success' | 'info'
- `label` - Custom label (optional)

---

## Usage Example

```vue
<script setup>
import {
  GRNFormHeader,
  GRNSearchSection,
  GRNItemsTable,
  GRNFormFooter,
  GRNSummary,
  GRNStatusBadge
} from '@/shared/components/GRN'
import type { TableColumn } from '@/shared/components/GRN'

const columns: TableColumn[] = [
  { key: 'itemCode', label: 'Item Code', width: 'w-32' },
  { key: 'description', label: 'Description' },
  { key: 'quantity', label: 'Qty', width: 'w-24', align: 'right' }
]
</script>

<template>
  <div>
    <GRNFormHeader
      title="Create GRN"
      :po-number="selectedPO?.DocNum"
      :vendor-name="selectedPO?.CardName"
      @back="router.back()"
    >
      <template #actions>
        <button class="btn">Custom Action</button>
      </template>
    </GRNFormHeader>

    <GRNSearchSection
      v-model:from-date="fromDate"
      v-model:to-date="toDate"
      v-model:bp-search="bpSearch"
      :loading="loading"
      :results-count="purchaseOrders.length"
      @fetch="loadPurchaseOrders"
    />

    <GRNSummary
      :completed-items="completedCount"
      :total-items="lineItems.length"
    />

    <GRNItemsTable
      :items="lineItems"
      :columns="columns"
      :editable-fields="['receivedQty', 'batchNo']"
      @update-item="handleItemUpdate"
      @delete-item="handleItemDelete"
    >
      <template #bulk-actions>
        <button @click="receiveAll">Receive All</button>
      </template>
    </GRNItemsTable>

    <GRNFormFooter
      :items-count="lineItems.length"
      :total-amount="totalAmount"
      :can-submit="isValid"
      :submitting="submitting"
      @submit="handleSubmit"
      @cancel="handleCancel"
    />
  </div>
</template>
```

---

## Column Definition

```typescript
interface TableColumn {
  key: string           // Field key (supports dot notation: 'item.code')
  label: string         // Column header label
  width?: string        // Tailwind width class (e.g., 'w-32')
  align?: 'left' | 'center' | 'right'  // Text alignment
  format?: (value: any, item: any) => string  // Custom formatter
}
```

---

## Benefits

1. **Consistency** - Same UI/UX across all plants
2. **Maintainability** - Fix once, deploy everywhere
3. **Type Safety** - Full TypeScript support
4. **Flexibility** - Extensive slot support for customization
5. **Accessibility** - Built-in keyboard shortcuts and ARIA labels
6. **Performance** - Optimized re-rendering with proper key usage

---

## Plant-Specific Customization

While these components are shared, plant-specific logic should remain in plant folders:

```
plants/
├── krishnagiri/
│   ├── components/
│   │   └── CreateGRNForm.vue   ← Uses shared components
│   └── composables/
│       └── useGRNLogic.ts      ← Plant-specific logic
├── malur/
│   ├── components/
│   │   └── CreateGRNForm.vue   ← Uses shared components
│   └── composables/
│       └── useGRNLogic.ts      ← Different logic if needed
```

---

## Migration Guide

### Before (1,677 lines):
```vue
<template>
  <!-- 1,677 lines of mixed UI and logic -->
</template>
```

### After (~200-300 lines):
```vue
<template>
  <GRNFormHeader />
  <GRNSearchSection />
  <GRNItemsTable />
  <GRNFormFooter />
</template>
```

**Result**: 85% reduction in component size! 🎉

