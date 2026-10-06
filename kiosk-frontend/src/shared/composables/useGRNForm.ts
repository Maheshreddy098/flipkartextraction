/**
 * Shared GRN Form Business Logic
 * Reusable composable for GRN form functionality across all plants
 * 
 * Features:
 * - PO selection and line item management
 * - Batch handling with validation
 * - Moisture content validation
 * - Field-level validation (invoice, dates, quantities)
 * - Recent POs history
 * - Common comments
 * - Keyboard shortcuts
 * - Auto-save drafts
 */

import { ref, computed, onMounted, watch } from 'vue'
import { useGRN } from '@/composables/useGRN'

export interface LineItem {
  LineNum: number
  ItemCode: string
  ItemDescription: string
  OrderedQuantity: number
  OpenQuantity: number
  ReceivedQuantity: number
  Quantity: number
  Price: number
  UnitMsr: string
  WarehouseCode: string
  AcctCode: string
  CostingCode: string
  MoistureValue?: number  // ✅ Added moisture field
  BatchLines: BatchLine[]
  validation?: {
    quantity?: {
      error?: string | null
      warning?: string | null
    }
    batch?: {
      error?: string | null
      warning?: string | null
    }
    hasError?: boolean  // ✅ General error flag
    hasWarning?: boolean  // ✅ General warning flag
  }
}

export interface BatchLine {
  BatchNumber: string
  Quantity: number
  MoistureValue?: number
  validation?: {
    batchNumber?: {
      error?: string | null
      warning?: string | null
    }
    quantity?: {
      error?: string | null
      warning?: string | null
    }
    moisture?: {
      error?: string | null
      warning?: string | null
    }
    error?: string | null  // ✅ General error field
    warning?: string | null  // ✅ General warning field
  }
}

export interface PurchaseOrder {
  DocEntry: number
  DocNum: string
  CardCode: string
  CardName: string
  DocDate?: string
  DocDueDate?: string
  DocTotal?: number
  lastUsed?: string
}

export function useGRNForm(plantId: string) {
  // Initialize frappe-ui composable for this plant
  const {
    purchaseOrders: poResource,
    poLineItems: lineItemsResource,
    createGRN: createGRNResource
  } = useGRN(plantId)

  // ==================== State ====================

  // Filter state
  const fetchAllPOs = ref(false)
  const fromDate = ref('')
  const toDate = ref('')
  const bpSearch = ref('')
  const loading = ref(false)

  // Data state
  const purchaseOrders = ref<PurchaseOrder[]>([])
  const selectedPO = ref<PurchaseOrder | null>(null)
  const lineItems = ref<LineItem[]>([])
  const invoiceNumber = ref('')
  const invoiceDate = ref('')
  const receivedDate = ref('')
  const createCNForLeftover = ref(false)
  const comments = ref('')
  const submitting = ref(false)

  // Validation state
  const showValidationDetails = ref(false)
  const fieldValidations = ref<{
    invoiceNumber: { error: string | null, warning: string | null }
    invoiceDate: { error: string | null, warning: string | null }
    receivedDate: { error: string | null, warning: string | null }
  }>({
    invoiceNumber: { error: null, warning: null },
    invoiceDate: { error: null, warning: null },
    receivedDate: { error: null, warning: null }
  })
  const acknowledgedWarningIds = ref<string[]>([])

  // UX Enhancement state
  const recentPOs = ref<PurchaseOrder[]>([])
  const commonComments = ref<string[]>([])
  const showFinalValidation = ref(false)
  const showShortcuts = ref(false)
  const startTime = ref<number | null>(null)

  // ==================== Quick Date Options ====================
  
  const quickDateOptions = [
    { days: 7, label: 'Last 7 days' },
    { days: 30, label: 'Last 30 days' },
    { days: 90, label: 'Last 90 days' }
  ]
  
  const setDefaultDateRange = () => {
    const today = new Date()
    const thirtyDaysAgo = new Date(today)
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

    toDate.value = today.toISOString().split('T')[0]
    fromDate.value = thirtyDaysAgo.toISOString().split('T')[0]
  }

  const setQuickDateRange = (days: number) => {
    const today = new Date()
    const startDate = new Date(today)
    startDate.setDate(startDate.getDate() - days)

    fromDate.value = startDate.toISOString().split('T')[0]
    toDate.value = today.toISOString().split('T')[0]
  }

  // ==================== Recent POs Management ====================
  
  const loadRecentPOs = () => {
    const stored = localStorage.getItem(`${plantId}_recent_pos`)
    if (stored) {
      recentPOs.value = JSON.parse(stored)
    }
  }
  
  const addToRecentPOs = (po: PurchaseOrder) => {
    const poWithTime: PurchaseOrder = { ...po, lastUsed: new Date().toISOString() }
    recentPOs.value = [
      poWithTime,
      ...recentPOs.value.filter((p: PurchaseOrder) => p.DocEntry !== po.DocEntry)
    ].slice(0, 10)
    localStorage.setItem(`${plantId}_recent_pos`, JSON.stringify(recentPOs.value))
  }
  
  const quickSelectPO = async (po: PurchaseOrder) => {
    selectedPO.value = po
    await loadPOLineItems()
    addToRecentPOs(po)
    showNotification('✅ PO loaded from recent history', 'success')
  }
  
  const clearRecentPOs = () => {
    if (confirm('Clear recent PO history?')) {
      recentPOs.value = []
      localStorage.setItem(`${plantId}_recent_pos`, JSON.stringify([]))
    }
  }

  // ==================== Common Comments ====================
  
  const loadCommonComments = () => {
    const stored = localStorage.getItem(`${plantId}_common_comments`)
    if (stored) {
      commonComments.value = JSON.parse(stored)
    } else {
      // Default comments
      commonComments.value = [
        'All items in good condition',
        'Partial delivery - remaining items expected next week',
        'Quality check required before acceptance',
        'Packaging damaged - items intact'
      ]
    }
  }
  
  const saveCommentToCommon = () => {
    if (comments.value && comments.value.trim() && !commonComments.value.includes(comments.value)) {
      commonComments.value.unshift(comments.value.trim())
      commonComments.value = commonComments.value.slice(0, 5)
      localStorage.setItem(`${plantId}_common_comments`, JSON.stringify(commonComments.value))
    }
  }

  // ==================== API Calls ====================
  
  const loadPurchaseOrders = async () => {
    try {
      loading.value = true
      
      // Use frappe-ui resource with proper parameters
      const params = {
        fromDate: fromDate.value || '',
        toDate: toDate.value || '',
        businessPartner: bpSearch.value || null,
        status: 'Open',
        fetchAll: fetchAllPOs.value
      }
      
      await poResource.fetch(params)
      
      if (poResource.data) {
        purchaseOrders.value = poResource.data
        showNotification(`✅ Found ${purchaseOrders.value.length} purchase orders`, 'success')
      } else {
        purchaseOrders.value = []
        showNotification('No purchase orders found', 'info')
      }
    } catch (error: any) {
      console.error('[Load POs] Error:', error)
      showNotification(`❌ Failed to load purchase orders: ${error?.message || error}`, 'error')
    } finally {
      loading.value = false
    }
  }

  const loadPOLineItems = async () => {
    if (!selectedPO.value) return

    try {
      loading.value = true
      
      // Use frappe-ui resource - pass DocEntry as poNo parameter
      await lineItemsResource.fetch(selectedPO.value.DocEntry)

      if (lineItemsResource.data) {
        const items = lineItemsResource.data

        // Initialize line items with proper structure
        lineItems.value = items.map((item: any) => ({
          ...item,
          ReceivedQuantity: 0,
          Quantity: 0,
          BatchLines: [],
          validation: {
            quantity: { error: null, warning: null },
            batch: { error: null, warning: null }
          }
        }))
        
        // Set received date to today
        receivedDate.value = new Date().toISOString().split('T')[0]

        showNotification(`✅ Loaded ${lineItems.value.length} line items`, 'success')
      }
    } catch (error: any) {
      console.error('[Load Line Items] Error:', error)
      showNotification(`❌ Failed to load PO line items: ${error?.message || error}`, 'error')
    } finally {
      loading.value = false
    }
  }

  const submitGRN = async () => {
    try {
      // Final validation
      if (!validateBeforeSubmit()) {
        return
      }
      
      if (!selectedPO.value) {
        showNotification('❌ No PO selected', 'error')
        return
      }
      
      submitting.value = true
      
      // Prepare GRN data (match backend expected field names!)
      const grnData = {
        po_doc_entry: selectedPO.value.DocEntry,  // ✅ Backend expects po_doc_entry
        vendor_code: selectedPO.value.CardCode,   // ✅ Backend expects vendor_code
        vendor_name: selectedPO.value.CardName,   // ✅ Backend expects vendor_name
        invoice_number: invoiceNumber.value,
        invoice_date: invoiceDate.value,
        received_date: receivedDate.value,
        comments: comments.value,
        create_cn_for_leftover: createCNForLeftover.value,
        lines: lineItems.value  // ✅ Backend expects 'lines' (it also accepts 'line_items')
          .filter((item: LineItem) => item.Quantity > 0)
          .map((item: LineItem) => ({
            line_num: item.LineNum,
            item_code: item.ItemCode,
            item_description: item.ItemDescription,
            received_quantity: item.Quantity,     // ✅ Backend expects received_quantity
            price: item.Price,
            warehouse_code: item.WarehouseCode,
            acct_code: item.AcctCode,
            costing_code: item.CostingCode,
            moisture_value: item.MoistureValue,   // ✅ Backend expects moisture_value
            batch_lines: (item.BatchLines || []).map((batch: BatchLine) => ({
              batch_number: batch.BatchNumber,    // ✅ Backend expects batch_number (snake_case)
              quantity: batch.Quantity,           // ✅ Backend expects quantity (lowercase)
              moisture_value: batch.MoistureValue // ✅ Backend expects moisture_value (snake_case)
            }))
          }))
      }
      
      // Submit using frappe-ui resource (send grnData directly, NOT wrapped!)
      await createGRNResource.submit(grnData)
      
      console.log('[Submit GRN] Response:', createGRNResource.data)
      
      if (createGRNResource.data) {
        const result = createGRNResource.data
        
        // Save comment to common comments
        saveCommentToCommon()
        
        // Show success message with GRN number
        const grnNumber = result.grn_number || result.message?.grn_number || 'Unknown'
        alert(`✅ GRN Posted to SAP Successfully!\n\nGRN Number: ${grnNumber}\n\nThe GRN has been created in SAP.`)
        
        // Redirect to GRN list after a short delay
        setTimeout(() => {
          window.location.href = `/kiosk/plant/${plantId}/grn`
        }, 1500)
      } else {
        // If no data returned, it might have failed silently
        throw new Error('No response data received from server. GRN may not have been posted to SAP.')
      }
    } catch (error: any) {
      console.error('[Submit GRN] Error:', error)
      alert(`❌ Failed to post GRN to SAP:\n\n${error?.message || error}\n\nPlease try again or contact support.`)
    } finally {
      submitting.value = false
    }
  }

  // ==================== Validation ====================
  
  const validateQuantity = (item: LineItem) => {
    try {
      if (!item.validation) item.validation = {}
      if (!item.validation.quantity) item.validation.quantity = {}
      
      item.validation.quantity.error = null
      item.validation.quantity.warning = null
      
      if (item.Quantity < 0) {
        item.validation.quantity.error = 'Quantity cannot be negative'
      } else if (item.Quantity > item.OpenQuantity) {
        item.validation.quantity.error = `Quantity (${item.Quantity}) exceeds open quantity (${item.OpenQuantity})`
      } else if (item.Quantity > 0 && item.Quantity < item.OpenQuantity * 0.1) {
        item.validation.quantity.warning = 'Receiving less than 10% of open quantity'
      }
      
      // Batch validation
      if (item.Quantity > 0 && (!item.BatchLines || item.BatchLines.length === 0)) {
        item.validation.batch = item.validation.batch || {}
        item.validation.batch.error = 'At least one batch is required'
      } else if (item.BatchLines && item.BatchLines.length > 0) {
        const totalBatchQty = item.BatchLines.reduce((sum: number, batch: BatchLine) => sum + (batch.Quantity || 0), 0)
        if (Math.abs(totalBatchQty - item.Quantity) > 0.01) {
          item.validation.batch = item.validation.batch || {}
          item.validation.batch.error = `Batch total (${totalBatchQty}) does not match item quantity (${item.Quantity})`
        } else {
          // ✅ Clear error when quantities match
          item.validation.batch = item.validation.batch || {}
          item.validation.batch.error = null
        }
      } else if (item.Quantity === 0 && item.validation.batch) {
        // ✅ Clear batch errors when quantity is 0
        item.validation.batch.error = null
      }
    } catch (error) {
      console.error('[Validate Quantity] Error:', error)
    }
  }
  
  const validateBatchNumber = (batch: BatchLine, item: LineItem) => {
    try {
      if (!batch.validation) batch.validation = {}
      if (!batch.validation.batchNumber) batch.validation.batchNumber = {}
      
      batch.validation.batchNumber.error = null
      batch.validation.batchNumber.warning = null
      
      if (!batch.BatchNumber || batch.BatchNumber.trim() === '') {
        batch.validation.batchNumber.error = 'Batch number is required'
      } else {
        // Check for duplicate batch numbers in the same item
        const duplicates = (item.BatchLines || []).filter((b: BatchLine) => b.BatchNumber === batch.BatchNumber)
        if (duplicates.length > 1) {
          batch.validation.batchNumber.error = 'Duplicate batch number'
        }
      }
    } catch (error) {
      console.error('[Validate Batch Number] Error:', error)
    }
  }
  
  const validateBatchQuantities = (item: LineItem) => {
    try {
      if (!item.validation) item.validation = {}
      if (!item.validation.batch) item.validation.batch = {}
      
      if (!item.BatchLines || item.BatchLines.length === 0) return
      
      const totalBatchQty = item.BatchLines.reduce((sum: number, batch: BatchLine) => sum + (batch.Quantity || 0), 0)
      
      if (Math.abs(totalBatchQty - item.Quantity) > 0.01) {
        item.validation.batch.error = `Batch total (${totalBatchQty}) does not match item quantity (${item.Quantity})`
      } else {
        item.validation.batch.error = null
      }
    } catch (error) {
      console.error('[Validate Batch Quantities] Error:', error)
    }
  }
  
  const validateBeforeSubmit = () => {
    // Validate header fields
    if (!invoiceNumber.value) {
      fieldValidations.value.invoiceNumber.error = 'Invoice number is required'
      showNotification('❌ Invoice number is required', 'error')
      return false
    }

    if (!invoiceDate.value) {
      fieldValidations.value.invoiceDate.error = 'Invoice date is required'
      showNotification('❌ Invoice date is required', 'error')
      return false
    }

    if (!receivedDate.value) {
      fieldValidations.value.receivedDate.error = 'Received date is required'
      showNotification('❌ Received date is required', 'error')
      return false
    }
    
    // Validate line items
    const itemsWithQuantity = lineItems.value.filter((item: LineItem) => item.Quantity > 0)
    
    if (itemsWithQuantity.length === 0) {
      showNotification('❌ At least one line item with quantity is required', 'error')
      return false
    }
    
    // Check for validation errors
    const errors = validationErrors.value
    if (errors.length > 0) {
      showValidationDetails.value = true
      showNotification(`❌ Please fix ${errors.length} error(s) before submitting`, 'error')
      return false
    }
    
    return true
  }

  // ==================== Computed Properties ====================
  
  const completedItems = computed(() => {
    try {
      return lineItems.value.filter((item: LineItem) => {
        const qty = item.Quantity || 0
        return qty > 0 && qty === item.OpenQuantity
      }).length
    } catch (error) {
      console.error('[Completed Items] Error:', error)
      return 0
    }
  })
  
  const partialItems = computed(() => {
    try {
      return lineItems.value.filter((item: LineItem) => {
        const qty = item.Quantity || 0
        return qty > 0 && qty < item.OpenQuantity
      }).length
    } catch (error) {
      console.error('[Partial Items] Error:', error)
      return 0
    }
  })
  
  const totalBatches = computed(() => {
    try {
      return lineItems.value.reduce((sum: number, item: LineItem) => {
        if (!item.BatchLines || !Array.isArray(item.BatchLines)) return sum
        return sum + item.BatchLines.length
      }, 0)
    } catch (error) {
      console.error('[Total Batches] Error:', error)
      return 0
    }
  })
  
  const validationErrors = computed(() => {
    try {
      const errors: any[] = []
      
      // Header validations
      if (fieldValidations.value.invoiceNumber.error) {
        errors.push({ id: 'inv_num', field: 'Invoice Number', message: fieldValidations.value.invoiceNumber.error })
      }
      if (fieldValidations.value.invoiceDate.error) {
        errors.push({ id: 'inv_date', field: 'Invoice Date', message: fieldValidations.value.invoiceDate.error })
      }
      if (fieldValidations.value.receivedDate.error) {
        errors.push({ id: 'rcv_date', field: 'Received Date', message: fieldValidations.value.receivedDate.error })
      }
      
      // Line item validations
      lineItems.value.forEach((item: LineItem, itemIndex: number) => {
        if (item.validation?.quantity?.error) {
          errors.push({
            id: `item_${itemIndex}_qty`,
            field: `${item.ItemCode} - Quantity`,
            message: item.validation.quantity.error
          })
        }
        if (item.validation?.batch?.error) {
          errors.push({
            id: `item_${itemIndex}_batch`,
            field: `${item.ItemCode} - Batch`,
            message: item.validation.batch.error
          })
        }
        
        // Batch validations
        if (item.BatchLines && Array.isArray(item.BatchLines)) {
          item.BatchLines.forEach((batch: BatchLine, batchIndex: number) => {
            if (batch.validation?.batchNumber?.error) {
              errors.push({
                id: `item_${itemIndex}_batch_${batchIndex}_num`,
                field: `${item.ItemCode} - Batch ${batchIndex + 1}`,
                message: batch.validation.batchNumber.error
              })
            }
            if (batch.validation?.quantity?.error) {
              errors.push({
                id: `item_${itemIndex}_batch_${batchIndex}_qty`,
                field: `${item.ItemCode} - Batch ${batchIndex + 1}`,
                message: batch.validation.quantity.error
              })
            }
            if (batch.validation?.moisture?.error) {
              errors.push({
                id: `item_${itemIndex}_batch_${batchIndex}_moisture`,
                field: `${item.ItemCode} - Batch ${batchIndex + 1} Moisture`,
                message: batch.validation.moisture.error
              })
            }
          })
        }
      })
      
      return errors
    } catch (error) {
      console.error('[Validation Errors] Error:', error)
      return []
    }
  })
  
  const validationWarnings = computed(() => {
    try {
      const warnings: any[] = []
      
      // Header warnings
      if (fieldValidations.value.invoiceNumber.warning && !acknowledgedWarningIds.value.includes('inv_num')) {
        warnings.push({ id: 'inv_num', field: 'Invoice Number', message: fieldValidations.value.invoiceNumber.warning })
      }
      
      // Line item warnings
      lineItems.value.forEach((item: LineItem, itemIndex: number) => {
        const warnId = `item_${itemIndex}_qty`
        if (item.validation?.quantity?.warning && !acknowledgedWarningIds.value.includes(warnId)) {
          warnings.push({
            id: warnId,
            field: `${item.ItemCode} - Quantity`,
            message: item.validation.quantity.warning
          })
        }
        
        // Batch warnings
        if (item.BatchLines && Array.isArray(item.BatchLines)) {
          item.BatchLines.forEach((batch: BatchLine, batchIndex: number) => {
            const batchWarnId = `item_${itemIndex}_batch_${batchIndex}_moisture`
            if (batch.validation?.moisture?.warning && !acknowledgedWarningIds.value.includes(batchWarnId)) {
              warnings.push({
                id: batchWarnId,
                field: `${item.ItemCode} - Batch ${batchIndex + 1} Moisture`,
                message: batch.validation.moisture.warning
              })
            }
          })
        }
      })
      
      return warnings
    } catch (error) {
      console.error('[Validation Warnings] Error:', error)
      return []
    }
  })
  
  const canSubmit = computed(() => {
    return selectedPO.value &&
           invoiceNumber.value &&
           invoiceDate.value &&
           receivedDate.value &&
           lineItems.value.some((item: LineItem) => item.Quantity > 0) &&
           validationErrors.value.length === 0 &&
           !submitting.value
  })

  // ==================== Helpers ====================
  
  function showNotification(message: string, type: 'success' | 'error' | 'info' = 'info') {
    // Use browser alert for now (can be replaced with toast library)
    if (type === 'error') {
      alert(`❌ ${message}`)
    } else if (type === 'success') {
      alert(`✅ ${message}`)
    } else {
      alert(message)
    }
  }
  
  function acknowledgeWarning(warningId: string) {
    acknowledgedWarningIds.value.push(warningId)
  }

  // ==================== Lifecycle ====================
  
  // Watch for changes and clear validation errors
  watch(invoiceNumber, (newVal) => {
    if (newVal && newVal.trim()) {
      fieldValidations.value.invoiceNumber.error = null
    }
  })
  
  watch(invoiceDate, (newVal) => {
    if (newVal) {
      fieldValidations.value.invoiceDate.error = null
    }
  })
  
  watch(receivedDate, (newVal) => {
    if (newVal) {
      fieldValidations.value.receivedDate.error = null
    }
  })

  onMounted(() => {
    setDefaultDateRange()
    loadRecentPOs()
    loadCommonComments()
    startTime.value = Date.now()
  })

  // ==================== Return ====================

  return {
    // State
    fetchAllPOs,
    fromDate,
    toDate,
    bpSearch,
    loading,
    purchaseOrders,
    selectedPO,
    lineItems,
    invoiceNumber,
    invoiceDate,
    receivedDate,
    createCNForLeftover,
    comments,
    submitting,
    showValidationDetails,
    fieldValidations,
    recentPOs,
    commonComments,
    showFinalValidation,
    showShortcuts,

    // Computed
    completedItems,
    partialItems,
    totalBatches,
    validationErrors,
    validationWarnings,
    canSubmit,
    
    // Methods - Date
    quickDateOptions,
    setQuickDateRange,
    
    // Methods - POs
    loadPurchaseOrders,
    loadPOLineItems,
    quickSelectPO,
    clearRecentPOs,
    
    // Methods - Submit
    submitGRN,
    
    // Methods - Validation
    validateQuantity,
    validateBatchNumber,
    validateBatchQuantities,
    acknowledgeWarning,
    
    // Methods - Comments
    saveCommentToCommon
  }
}
