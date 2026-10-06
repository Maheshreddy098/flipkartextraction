<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Top bar -->
    <div class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Ghee Reverse Production Order</h1>
        <p class="text-xs text-gray-400 mt-0.5">Convert finished goods → raw materials via SAP B1</p>
      </div>
      <div v-if="gpoName" class="flex items-center gap-2">
        <span class="text-xs text-gray-400">Record:</span>
        <span class="font-mono text-xs font-semibold text-yellow-700 bg-yellow-50 px-2.5 py-1 rounded-full border border-yellow-200">
          {{ gpoName }}
        </span>
      </div>
    </div>

    <div class="flex gap-0 max-w-[1400px] mx-auto">

      <!-- ─── Main scrollable form ─────────────────────────────────── -->
      <div class="flex-1 p-6 space-y-4 min-w-0">

        <!-- Global error -->
        <div
          v-if="error"
          class="p-4 bg-red-50 border border-red-300 rounded-xl text-red-700 text-sm flex items-start gap-2"
        >
          <span class="font-bold flex-shrink-0">Error:</span>
          <span class="flex-1">{{ error }}</span>
          <button @click="error = ''" class="text-red-400 hover:text-red-600">✕</button>
        </div>

        <!-- ══════════════════════════════════════════════
             SECTION 1 — Source FG & Batches
        ══════════════════════════════════════════════ -->
        <section :class="sectionClass(1)">
          <div class="flex items-center gap-3 mb-5">
            <div :class="stepDot(1)">
              <span v-if="currentStep > 1">✓</span><span v-else>1</span>
            </div>
            <h2 class="text-base font-semibold text-gray-800">Source Finished Good &amp; Batch Selection</h2>
            <span v-if="currentStep > 1" class="ml-auto text-xs text-green-600 font-medium bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
              Done — {{ sourceFGItems.filter(i => i.available_batches.some(b => Number(i.batch_qtys?.[`${b.batch_number}|${b.warehouse}`] || 0) > 0)).length }} item(s), {{ allSelectedBatches.length }} batch{{ allSelectedBatches.length !== 1 ? 'es' : '' }}, qty {{ totalSourceQty }}
            </span>
          </div>

          <div :class="{ 'opacity-60 pointer-events-none': currentStep > 1 }">
            <div class="space-y-4">

              <!-- FG item cards — one per source item -->
              <div
                v-for="(item, idx) in sourceFGItems"
                :key="idx"
                class="border-2 border-gray-200 rounded-xl p-4 space-y-3 bg-gray-50/50"
              >
                <!-- Card header -->
                <div class="flex items-center gap-2">
                  <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">FG Item {{ idx + 1 }}</span>
                  <button
                    v-if="sourceFGItems.length > 1"
                    @click="removeFGItem(idx)"
                    class="ml-auto text-red-300 hover:text-red-500 text-xs px-2 py-0.5 rounded hover:bg-red-50 transition-colors"
                  >✕ Remove</button>
                </div>

                <!-- Item code + fetch -->
                <div class="flex gap-3">
                  <input
                    :value="item.item_code"
                    @input="item.item_code = $event.target.value.toUpperCase()"
                    type="text"
                    placeholder="e.g. FGHN0132"
                    class="flex-1 px-4 py-2.5 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-yellow-500 text-gray-900 uppercase bg-white"
                    @keyup.enter="fetchBatchesFor(idx)"
                  />
                  <button
                    @click="fetchBatchesFor(idx)"
                    :disabled="!item.item_code.trim() || item.loading"
                    class="px-5 py-2.5 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600
                           disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    <span v-if="item.loading" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block" />
                    {{ item.loading ? 'Fetching…' : 'Fetch Batches' }}
                  </button>
                </div>

                <!-- No batches found -->
                <div v-if="item.loaded && item.available_batches.length === 0" class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
                  No batches found for "{{ item.item_code }}" in warehouse HN-WIP.
                </div>

                <!-- Inline batch table — qty inputs for each batch, pre-filled -->
                <div v-if="item.available_batches.length > 0" class="rounded-lg border border-gray-200 overflow-hidden bg-white">
                  <!-- Table toolbar -->
                  <div class="flex items-center px-3 py-2 bg-gray-50 border-b border-gray-200 gap-2 text-xs">
                    <span class="text-gray-500 font-medium">{{ item.available_batches.length }} batch{{ item.available_batches.length !== 1 ? 'es' : '' }}</span>
                    <button @click="selectAllBatchesFor(idx)" class="ml-auto text-yellow-600 hover:text-yellow-800 font-medium hover:underline">Select All</button>
                    <span class="text-gray-300">|</span>
                    <button @click="clearAllBatchesFor(idx)" class="text-gray-400 hover:text-gray-600 hover:underline">Clear All</button>
                  </div>
                  <table class="w-full text-sm">
                    <thead class="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th class="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Batch</th>
                        <th class="text-left px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Warehouse</th>
                        <th class="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Available</th>
                        <th class="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">₹/unit</th>
                        <th class="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Use Qty</th>
                        <th class="text-right px-3 py-2 text-xs font-semibold text-gray-500 uppercase">Line Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="b in item.available_batches"
                        :key="`${b.batch_number}|${b.warehouse}`"
                        class="border-b border-gray-100 last:border-0 transition-colors"
                        :class="Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0 ? 'bg-yellow-50/40' : ''"
                      >
                        <td class="px-3 py-2 font-mono text-xs text-gray-800">{{ b.batch_number }}</td>
                        <td class="px-3 py-2 text-xs font-mono text-blue-700">{{ b.warehouse }}</td>
                        <td class="px-3 py-2 text-right text-gray-500 text-xs">{{ b.quantity }}</td>
                        <td class="px-3 py-2 text-right text-gray-500 text-xs">₹{{ b.calc_price }}</td>
                        <td class="px-3 py-2 text-right">
                          <input
                            v-model.number="item.batch_qtys[`${b.batch_number}|${b.warehouse}`]"
                            type="number"
                            min="0"
                            :max="b.quantity"
                            step="any"
                            placeholder="0"
                            class="w-24 px-2 py-1 border-2 rounded-lg text-right text-sm focus:outline-none transition-colors"
                            :class="batchQtyOver(item, b)
                              ? 'border-red-400 text-red-700'
                              : Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0
                                ? 'border-yellow-400 focus:border-yellow-500 text-gray-900 font-semibold'
                                : 'border-gray-200 focus:border-yellow-400 text-gray-400'"
                          />
                        </td>
                        <td class="px-3 py-2 text-right font-semibold text-yellow-700 text-xs">
                          <span v-if="Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0">
                            ₹{{ (Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`]) * b.calc_price).toFixed(3) }}
                          </span>
                          <span v-else class="text-gray-300">—</span>
                        </td>
                      </tr>
                    </tbody>
                    <tfoot class="bg-gray-50 border-t-2 border-gray-200">
                      <tr>
                        <td colspan="3" class="px-3 py-2 text-xs font-semibold text-gray-500">Selected total</td>
                        <td class="px-3 py-2 text-right font-bold text-gray-900">{{ itemSelectedQty(item) }}</td>
                        <td class="px-3 py-2 text-right font-bold text-yellow-800">₹{{ itemSelectedCost(item).toFixed(3) }}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>

              <!-- Add another FG item button -->
              <button
                @click="addFGItem"
                class="w-full py-2.5 border-2 border-dashed border-yellow-300 text-yellow-700 font-medium rounded-xl hover:border-yellow-500 hover:bg-yellow-50 transition-colors text-sm"
              >
                + Add Another FG Item Code
              </button>

              <!-- Grand total across all items -->
              <div v-if="totalBatchCost > 0" class="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3 flex flex-wrap gap-6 text-sm">
                <span class="text-yellow-700">
                  <span class="text-gray-500">Total qty:</span> <strong>{{ totalSourceQty }}</strong>
                </span>
                <span class="text-yellow-800">
                  <span class="text-gray-500">Total cost:</span> <strong>₹{{ totalBatchCost.toFixed(3) }}</strong>
                </span>
                <span class="text-gray-500 text-xs">
                  {{ sourceFGItems.filter(i => i.available_batches.some(b => Number(i.batch_qtys?.[`${b.batch_number}|${b.warehouse}`] || 0) > 0)).length }} item(s),
                  {{ allSelectedBatches.length }} batch{{ allSelectedBatches.length !== 1 ? 'es' : '' }}
                </span>
              </div>

            </div>

            <div v-if="currentStep === 1" class="mt-5 flex justify-end">
              <button
                @click="step1Next"
                :disabled="allSelectedBatches.length === 0"
                class="px-6 py-2.5 bg-yellow-500 text-white font-semibold rounded-lg hover:bg-yellow-600
                       disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                Confirm & Continue →
              </button>
            </div>
          </div>

          <!-- Edit button when step is done -->
          <div v-if="currentStep > 1" class="mt-3 flex justify-end">
            <button @click="goTo(1)" class="text-xs text-gray-400 hover:text-yellow-600 underline transition-colors">
              Edit
            </button>
          </div>
        </section>

        <!-- ══════════════════════════════════════════════
             SECTION 2 — BOM & Cost Split
        ══════════════════════════════════════════════ -->
        <section :class="sectionClass(2)">
          <!-- Locked overlay header -->
          <div v-if="currentStep < 2" class="flex items-center gap-3">
            <div :class="stepDot(2)">2</div>
            <h2 class="text-base font-semibold text-gray-400">New FG Item &amp; Cost Split</h2>
            <span class="ml-auto text-xs text-gray-300">Complete step 1 first</span>
          </div>

          <template v-else>
            <div class="flex items-center gap-3 mb-5">
              <div :class="stepDot(2)">
                <span v-if="currentStep > 2">✓</span><span v-else>2</span>
              </div>
              <h2 class="text-base font-semibold text-gray-800">New FG Item &amp; Cost Split</h2>
              <span v-if="currentStep > 2 && costSplit" class="ml-auto text-xs text-green-600 font-medium bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
                Done — {{ costSplit.bom_lines?.length }} lines loaded
              </span>
            </div>

            <div :class="{ 'opacity-60 pointer-events-none': currentStep > 2 }">
              <div class="space-y-4">
                <div class="flex gap-3">
                  <div class="flex-1">
                    <label class="block text-sm font-medium text-gray-700 mb-1">
                      Output Item Code <span class="text-red-500">*</span>
                    </label>
                    <input
                      :value="form.newItemCode"
                      @input="form.newItemCode = $event.target.value.toUpperCase()"
                      type="text"
                      placeholder="Item code for the output FG (e.g. RMHN0094)"
                      class="w-full px-4 py-2.5 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-yellow-500 text-gray-900 uppercase bg-white"
                    />
                  </div>
                  <div class="flex items-end">
                    <button
                      @click="fetchBomSplit"
                      :disabled="!form.newItemCode.trim() || loadingBomSplit"
                      class="px-5 py-2.5 bg-yellow-500 text-white font-medium rounded-lg hover:bg-yellow-600
                             disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                    >
                      <span v-if="loadingBomSplit" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block" />
                      {{ loadingBomSplit ? 'Loading…' : 'Load BOM & Split' }}
                    </button>
                  </div>
                </div>

                <div v-if="bomMessage && (!costSplit || costSplit.bom_lines.length === 0)" class="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800 text-sm">
                  ⚠️ {{ bomMessage }}
                </div>

                <div v-if="costSplit && costSplit.bom_lines.length > 0">
                  <div class="flex flex-wrap gap-4 text-sm bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 mb-3 text-gray-900">
                    <span><span class="text-gray-500">Batch cost:</span> <strong class="text-gray-900 ml-1">₹{{ costSplit.batch_cost }}</strong></span>
                    <span><span class="text-gray-500">Qty:</span> <strong class="text-gray-900 ml-1">{{ costSplit.batch_qty }}</strong></span>
                    <span><span class="text-gray-500">Original PO:</span> <strong class="text-gray-900 ml-1">{{ costSplit.original_po_entry || '—' }}</strong></span>
                  </div>
                  <div class="overflow-x-auto rounded-lg border border-gray-200">
                    <!-- Table toolbar -->
                    <div class="flex items-center px-4 py-2 bg-gray-50 border-b border-gray-200 gap-3 text-xs">
                      <span class="text-gray-500 font-medium">{{ costSplit.bom_lines.length }} BOM line{{ costSplit.bom_lines.length !== 1 ? 's' : '' }}</span>
                      <button
                        v-if="!editingBom"
                        @click="editingBom = true"
                        class="ml-auto flex items-center gap-1 text-yellow-600 hover:text-yellow-800 font-medium hover:underline"
                      >✏ Edit rows</button>
                      <button
                        v-else
                        @click="saveBomEdits"
                        class="ml-auto flex items-center gap-1 text-green-600 hover:text-green-800 font-semibold hover:underline"
                      >✓ Done editing</button>
                    </div>
                    <table class="w-full text-sm">
                      <thead class="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Item</th>
                          <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Name</th>
                          <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Qty</th>
                          <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Unit Price</th>
                          <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Line Cost</th>
                          <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Warehouse</th>
                          <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Source</th>
                          <th v-if="editingBom" class="w-8"></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(line, lineIdx) in costSplit.bom_lines"
                          :key="lineIdx"
                          :class="['border-b border-gray-100 last:border-0', line.warehouse?.includes('SCRAP') ? 'bg-orange-50/50' : editingBom ? 'bg-yellow-50/30' : 'hover:bg-gray-50']"
                        >
                          <!-- Item code — editable in edit mode -->
                          <td class="px-4 py-2 font-mono text-xs text-gray-700">
                            <input
                              v-if="editingBom"
                              :value="line.item_code"
                              @input="line.item_code = $event.target.value.toUpperCase()"
                              type="text"
                              class="w-28 px-2 py-1 border-2 border-yellow-300 rounded text-xs font-mono focus:outline-none focus:border-yellow-500 uppercase bg-white text-gray-900"
                            />
                            <span v-else>{{ line.item_code }}</span>
                          </td>
                          <!-- Item name — editable -->
                          <td class="px-4 py-2 text-gray-700 text-sm">
                            <input
                              v-if="editingBom"
                              v-model="line.item_name"
                              type="text"
                              class="w-40 px-2 py-1 border-2 border-yellow-300 rounded text-sm focus:outline-none focus:border-yellow-500 bg-white text-gray-900"
                            />
                            <span v-else>{{ line.item_name }}</span>
                          </td>

                          <!-- Qty -->
                          <td class="px-4 py-2 text-right">
                            <input
                              v-if="editingBom"
                              v-model.number="line.quantity"
                              type="number" step="any" min="0"
                              class="w-24 px-2 py-1 border-2 border-yellow-300 rounded text-right text-sm font-semibold focus:outline-none focus:border-yellow-500 bg-white text-gray-900"
                            />
                            <span v-else class="text-gray-700">{{ line.quantity }}</span>
                          </td>

                          <!-- Unit price — read-only; FG remainder live-recomputes -->
                          <td class="px-4 py-2 text-right">
                            <span class="text-gray-700">₹{{ editingBom ? liveUnitPrice(line) : line.unit_price }}</span>
                          </td>

                          <!-- Line cost — live-computed when editing -->
                          <td class="px-4 py-2 text-right font-semibold text-green-700">
                            ₹{{ editingBom ? liveLineCost(line) : line.line_cost }}
                          </td>

                          <!-- Warehouse -->
                          <td class="px-4 py-2 text-xs">
                            <input
                              v-if="editingBom"
                              v-model="line.warehouse"
                              type="text"
                              class="w-32 px-2 py-1 border-2 border-yellow-300 rounded text-xs font-mono focus:outline-none focus:border-yellow-500 bg-white text-gray-900"
                            />
                            <span v-else :class="line.warehouse?.includes('SCRAP') ? 'text-orange-600 font-medium' : 'text-gray-500'">{{ line.warehouse }}</span>
                          </td>

                          <td class="px-4 py-2">
                            <span :class="['text-xs px-2 py-0.5 rounded-full font-medium',
                              line.cost_source === 'remainder'    ? 'bg-blue-100 text-blue-700' :
                              line.cost_source === 'po_ige1'      ? 'bg-green-100 text-green-700' :
                              line.cost_source === 'minimum_0.01' ? 'bg-orange-100 text-orange-700' :
                              'bg-gray-100 text-gray-600']">{{ line.cost_source }}</span>
                          </td>

                          <!-- Remove row button (edit mode only) -->
                          <td v-if="editingBom" class="px-2 py-2">
                            <button
                              @click="removeBomRow(lineIdx)"
                              class="text-red-300 hover:text-red-600 text-sm font-bold leading-none hover:bg-red-50 w-6 h-6 rounded flex items-center justify-center"
                              title="Remove row"
                            >✕</button>
                          </td>
                        </tr>

                        <!-- Add row button row (edit mode) -->
                        <tr v-if="editingBom">
                          <td colspan="8" class="px-4 py-2">
                            <button
                              @click="addBomRow"
                              class="text-xs text-yellow-600 hover:text-yellow-800 font-medium flex items-center gap-1 hover:underline"
                            >＋ Add row</button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div v-if="currentStep === 2" class="mt-5 flex justify-end">
                <button
                  @click="goTo(3)"
                  :disabled="!costSplit || costSplit.bom_lines.length === 0"
                  class="px-6 py-2.5 bg-yellow-500 text-white font-semibold rounded-lg hover:bg-yellow-600
                         disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  Confirm & Continue →
                </button>
              </div>
            </div>

            <div v-if="currentStep > 2" class="mt-3 flex justify-end">
              <button @click="goTo(2)" class="text-xs text-gray-400 hover:text-yellow-600 underline transition-colors">Edit</button>
            </div>
          </template>
        </section>

        <!-- ══════════════════════════════════════════════
             SECTION 3 — Output Batch Numbers
        ══════════════════════════════════════════════ -->
        <section :class="sectionClass(3)">
          <div v-if="currentStep < 3" class="flex items-center gap-3">
            <div :class="stepDot(3)">3</div>
            <h2 class="text-base font-semibold text-gray-400">Output Batch Numbers</h2>
            <span class="ml-auto text-xs text-gray-300">Complete step 2 first</span>
          </div>

          <template v-else>
            <div class="flex items-center gap-3 mb-5">
              <div :class="stepDot(3)">
                <span v-if="currentStep > 3">✓</span><span v-else>3</span>
              </div>
              <h2 class="text-base font-semibold text-gray-800">Output Batch Numbers</h2>
              <span v-if="currentStep > 3" class="ml-auto text-xs text-green-600 font-medium bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
                Done
              </span>
            </div>

            <div :class="{ 'opacity-60 pointer-events-none': currentStep > 3 }">
              <p class="text-sm text-gray-500 mb-4">Enter a batch number for each output item. Required to continue.</p>

              <div class="overflow-x-auto rounded-lg border border-gray-200 mb-4">
                <table class="w-full text-sm">
                  <thead class="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Item</th>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Name</th>
                      <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Qty</th>
                      <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Price</th>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Warehouse</th>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Batch Number <span class="text-red-400">*</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="line in costSplit?.bom_lines || []"
                      :key="line.item_code"
                      class="border-b border-gray-100 last:border-0"
                    >
                      <td class="px-4 py-2.5 font-mono text-xs text-gray-700">{{ line.item_code }}</td>
                      <td class="px-4 py-2.5 text-gray-700 text-sm">{{ line.item_name }}</td>
                      <td class="px-4 py-2.5 text-right text-gray-700">{{ line.quantity }}</td>
                      <td class="px-4 py-2.5 text-right text-gray-700">₹{{ liveUnitPrice(line) }}</td>
                      <td class="px-4 py-2.5 text-xs">
                        <span :class="line.warehouse?.includes('SCRAP') ? 'text-orange-600 font-medium' : 'text-gray-500'">{{ line.warehouse }}</span>
                      </td>
                      <td class="px-4 py-2">
                        <input
                          v-model="outputBatchNos[line.item_code]"
                          type="text"
                          class="w-52 px-3 py-1.5 border-2 border-gray-200 rounded-lg text-xs focus:outline-none focus:border-yellow-500 bg-white text-gray-900"
                          :placeholder="`Batch for ${line.item_code}`"
                        />
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- Date + remarks -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Posting Date</label>
                  <input
                    v-model="form.docDate"
                    type="date"
                    class="w-full px-4 py-2.5 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-yellow-500 text-gray-900 bg-white"
                  />
                </div>
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1">Remarks</label>
                  <input
                    v-model="form.remarks"
                    type="text"
                    placeholder="Optional remarks for SAP"
                    class="w-full px-4 py-2.5 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-yellow-500 text-gray-900 bg-white"
                  />
                </div>
              </div>

              <div v-if="currentStep === 3" class="mt-5 flex justify-end">
                <button
                  @click="goTo(4)"
                  :disabled="!allBatchNosEntered"
                  class="px-6 py-2.5 bg-yellow-500 text-white font-semibold rounded-lg hover:bg-yellow-600
                         disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors"
                >
                  Review Order →
                </button>
              </div>
            </div>

            <div v-if="currentStep > 3" class="mt-3 flex justify-end">
              <button @click="goTo(3)" class="text-xs text-gray-400 hover:text-yellow-600 underline transition-colors">Edit</button>
            </div>
          </template>
        </section>

        <!-- ══════════════════════════════════════════════
             SECTION 4 — Review & Create PO
        ══════════════════════════════════════════════ -->
        <section :class="sectionClass(4)">
          <div v-if="currentStep < 4" class="flex items-center gap-3">
            <div :class="stepDot(4)">4</div>
            <h2 class="text-base font-semibold text-gray-400">Review &amp; Create Production Order</h2>
            <span class="ml-auto text-xs text-gray-300">Complete step 3 first</span>
          </div>

          <template v-else>
            <div class="flex items-center gap-3 mb-5">
              <div :class="stepDot(4)">
                <span v-if="currentStep > 4">✓</span><span v-else>4</span>
              </div>
              <h2 class="text-base font-semibold text-gray-800">Review &amp; Create Production Order</h2>
              <span v-if="currentStep > 4 && poResult" class="ml-auto text-xs text-green-600 font-medium bg-green-50 px-2.5 py-1 rounded-full border border-green-200">
                PO# {{ poResult.po_doc_num }} Created ✓
              </span>
            </div>

            <div :class="{ 'opacity-60 pointer-events-none': currentStep > 4 }">
              <!-- Component summary — one block per FG item -->
              <div class="bg-gray-50 rounded-lg border border-gray-200 p-4 mb-4 text-sm space-y-3">
                <p class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Components to issue from stock</p>
                <div class="flex flex-wrap gap-4 text-xs text-gray-600 border-b border-gray-200 pb-2 mb-2">
                  <span><span class="text-gray-400">Total qty:</span> <strong class="text-gray-900">{{ totalSourceQty }}</strong></span>
                  <span><span class="text-gray-400">Total cost:</span> <strong class="text-yellow-700">₹{{ totalBatchCost.toFixed(3) }}</strong></span>
                </div>
                <div v-for="(item, idx) in sourceFGItems.filter(i => i.available_batches.some(b => Number(i.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0))" :key="item.item_code" class="space-y-1">
                  <div class="flex items-center gap-3">
                    <span class="font-mono font-semibold text-gray-800 text-xs bg-yellow-50 border border-yellow-200 px-2 py-0.5 rounded">{{ item.item_code }}</span>
                    <span class="text-xs text-gray-500">qty {{ itemSelectedQty(item) }}</span>
                    <span class="text-xs text-yellow-700">₹{{ itemSelectedCost(item).toFixed(3) }}</span>
                  </div>
                  <div
                    v-for="b in item.available_batches.filter(b => Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0)"
                    :key="b.batch_number"
                    class="flex gap-4 text-xs text-gray-500 pl-4 border-l-2 border-yellow-200"
                  >
                    <span class="font-mono">{{ b.batch_number }}</span>
                    <span>{{ b.warehouse }}</span>
                    <span>qty: {{ Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`]) }}</span>
                    <span>₹{{ (Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`]) * b.calc_price).toFixed(3) }}</span>
                  </div>
                </div>
              </div>

              <!-- Output lines -->
              <div class="overflow-x-auto rounded-lg border border-gray-200 mb-5">
                <table class="w-full text-sm">
                  <thead class="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Item</th>
                      <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Qty</th>
                      <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Unit Price</th>
                      <th class="text-right px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Line Cost</th>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Warehouse</th>
                      <th class="text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase">Batch</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="line in costSplit?.bom_lines || []" :key="line.item_code" class="border-b border-gray-100 last:border-0">
                      <td class="px-4 py-2.5">
                        <div class="font-mono text-xs text-gray-700">{{ line.item_code }}</div>
                        <div class="text-gray-400 text-xs">{{ line.item_name }}</div>
                      </td>
                      <td class="px-4 py-2.5 text-right text-gray-700">{{ line.quantity }}</td>
                      <td class="px-4 py-2.5 text-right text-gray-700">₹{{ liveUnitPrice(line) }}</td>
                      <td class="px-4 py-2.5 text-right font-semibold text-green-700">₹{{ liveLineCost(line) }}</td>
                      <td class="px-4 py-2.5 text-xs">
                        <span :class="line.warehouse?.includes('SCRAP') ? 'text-orange-600 font-medium' : 'text-gray-500'">{{ line.warehouse }}</span>
                      </td>
                      <td class="px-4 py-2.5 font-mono text-xs text-gray-600">{{ outputBatchNos[line.item_code] }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div v-if="currentStep === 4" class="flex justify-end">
                <button
                  @click="submitCreatePO"
                  :disabled="creatingPO"
                  class="px-8 py-2.5 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700
                         disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                >
                  <span v-if="creatingPO" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block" />
                  {{ creatingPO ? 'Creating SAP Production Order…' : 'Create Production Order in SAP' }}
                </button>
              </div>
            </div>
          </template>
        </section>

        <!-- ══════════════════════════════════════════════
             SECTION 5 — Complete Production
        ══════════════════════════════════════════════ -->
        <section :class="sectionClass(5)">
          <div v-if="currentStep < 5" class="flex items-center gap-3">
            <div :class="stepDot(5)">5</div>
            <h2 class="text-base font-semibold text-gray-400">Complete Production (GI + GR + Close)</h2>
            <span class="ml-auto text-xs text-gray-300">Create PO first</span>
          </div>

          <template v-else>
            <div class="flex items-center gap-3 mb-5">
              <div :class="stepDot(5)">
                <span v-if="completionResult">✓</span><span v-else>5</span>
              </div>
              <h2 class="text-base font-semibold text-gray-800">Complete Production</h2>
            </div>

            <!-- PO created banner -->
            <div class="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 mb-4 text-sm flex gap-6">
              <span class="text-blue-700">SAP PO: <strong class="font-mono">{{ poResult?.po_doc_num }}</strong></span>
              <span class="text-blue-600 text-xs">DocEntry: {{ poResult?.po_entry }}</span>
            </div>

            <!-- Pre-completion checklist -->
            <div v-if="!completionResult" class="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-5 text-sm text-amber-800">
              <p class="font-semibold mb-3">This action will execute in SAP B1:</p>
              <ol class="space-y-2 list-none">
                <li class="flex items-start gap-2">
                  <span class="flex-shrink-0 w-5 h-5 rounded-full bg-amber-200 text-amber-800 text-xs flex items-center justify-center font-bold">1</span>
                  <span>
                    <strong>Goods Issue</strong> —
                    <template v-for="(item, idx) in sourceFGItems.filter(i => i.available_batches.some(b => Number(i.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0))" :key="item.item_code">
                      <strong class="font-mono">{{ item.item_code }}</strong>
                      ({{ item.available_batches.filter(b => Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0).length }} batch{{ item.available_batches.filter(b => Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0).length !== 1 ? 'es' : '' }})
                      <span v-if="idx < sourceFGItems.filter(i => i.available_batches.some(b => Number(i.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > 0)).length - 1">, </span>
                    </template>
                    — total qty {{ totalSourceQty }}
                  </span>
                </li>
                <li class="flex items-start gap-2">
                  <span class="flex-shrink-0 w-5 h-5 rounded-full bg-amber-200 text-amber-800 text-xs flex items-center justify-center font-bold">2</span>
                  <div>
                    <strong>Goods Receipt</strong> — receive {{ costSplit?.bom_lines?.length || 0 }} items:
                    <ul class="mt-1.5 ml-2 space-y-0.5">
                      <li v-for="line in costSplit?.bom_lines || []" :key="line.item_code" class="text-xs text-amber-700 flex gap-2">
                        <span class="font-mono font-semibold">{{ line.item_code }}</span>
                        <span>qty {{ line.quantity }}</span>
                        <span class="text-amber-500">→ {{ line.warehouse }}</span>
                        <span class="text-amber-600">({{ outputBatchNos[line.item_code] || 'auto' }})</span>
                      </li>
                    </ul>
                  </div>
                </li>
                <li class="flex items-start gap-2">
                  <span class="flex-shrink-0 w-5 h-5 rounded-full bg-amber-200 text-amber-800 text-xs flex items-center justify-center font-bold">3</span>
                  <span><strong>Close</strong> Production Order PO# {{ poResult?.po_doc_num }}</span>
                </li>
              </ol>
            </div>

            <!-- Completion result -->
            <div v-if="completionResult" class="bg-green-50 border border-green-300 rounded-xl p-5 mb-5">
              <p class="font-bold text-green-800 text-base mb-3">Production Complete ✓</p>
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm mb-3">
                <div class="bg-white rounded-lg border border-green-200 px-4 py-3">
                  <div class="text-xs text-green-500 mb-1">Goods Issue</div>
                  <div class="font-mono font-bold text-green-800">{{ completionResult.goods_issue_doc }}</div>
                </div>
                <div class="bg-white rounded-lg border border-green-200 px-4 py-3">
                  <div class="text-xs text-green-500 mb-1">Goods Receipt</div>
                  <div class="font-mono font-bold text-green-800">{{ completionResult.goods_receipt_doc }}</div>
                </div>
                <div class="bg-white rounded-lg border border-green-200 px-4 py-3">
                  <div class="text-xs text-green-500 mb-1">PO Closed</div>
                  <div class="font-semibold" :class="completionResult.po_closed ? 'text-green-700' : 'text-amber-600'">
                    {{ completionResult.po_closed ? 'Yes ✓' : 'Check SAP' }}
                  </div>
                </div>
              </div>
              <div v-if="completionResult.cost_summary" class="flex flex-wrap gap-4 text-xs text-green-700 pt-3 border-t border-green-200">
                <span>GI: <strong>₹{{ completionResult.cost_summary.total_gi_cost }}</strong></span>
                <span>GR: <strong>₹{{ completionResult.cost_summary.total_gr_cost }}</strong></span>
                <span>Jar: <strong>₹{{ completionResult.cost_summary.jar_cost }}</strong></span>
                <span>Scrap: <strong>₹{{ completionResult.cost_summary.scrap_cost }}</strong></span>
                <span>{{ form.newItemCode }} residual: <strong>₹{{ completionResult.cost_summary.fg_residual }}</strong></span>
                <span :class="completionResult.cost_summary.balanced ? 'text-green-700 font-bold' : 'text-red-600 font-bold'">
                  {{ completionResult.cost_summary.balanced ? '✓ Balanced' : '⚠ Mismatch!' }}
                </span>
              </div>
            </div>

            <div class="flex gap-3 justify-end">
              <button
                v-if="completionResult"
                @click="resetForm"
                class="px-6 py-2.5 bg-yellow-500 text-white font-semibold rounded-lg hover:bg-yellow-600 transition-colors"
              >
                + New Production Order
              </button>
              <button
                v-if="!completionResult"
                @click="submitComplete"
                :disabled="completing"
                class="px-8 py-2.5 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700
                       disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                <span v-if="completing" class="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full inline-block" />
                {{ completing ? 'Processing in SAP…' : 'Complete Production' }}
              </button>
            </div>
          </template>
        </section>

      </div>

      <!-- ─── Right sidebar — sticky progress tracker ───────────────── -->
      <div class="w-72 flex-shrink-0 p-6">
        <div class="sticky top-6 space-y-4">

          <!-- Step progress -->
          <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">Progress</h3>
            <div class="space-y-3">
              <div
                v-for="(s, i) in steps"
                :key="i"
                :class="['flex items-center gap-3 cursor-pointer group', currentStep < i + 1 ? 'opacity-50 cursor-default' : '']"
                @click="currentStep >= i + 1 && currentStep !== i + 1 ? goTo(i + 1) : null"
              >
                <div :class="[
                  'flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors',
                  currentStep > i + 1
                    ? 'bg-green-500 text-white'
                    : currentStep === i + 1
                      ? 'bg-yellow-500 text-white'
                      : 'bg-gray-100 text-gray-400'
                ]">
                  <span v-if="currentStep > i + 1">✓</span>
                  <span v-else>{{ i + 1 }}</span>
                </div>
                <div class="flex-1 min-w-0">
                  <div :class="['text-sm font-medium truncate', currentStep === i + 1 ? 'text-gray-900' : currentStep > i + 1 ? 'text-gray-500' : 'text-gray-300']">
                    {{ s }}
                  </div>
                  <div v-if="currentStep === i + 1" class="text-xs text-yellow-600 font-medium">Active</div>
                  <div v-else-if="currentStep > i + 1" class="text-xs text-green-500">Done</div>
                </div>
              </div>
            </div>
          </div>

          <!-- GPO record card -->
          <div v-if="gpoName" class="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Record</h3>
            <div class="font-mono text-sm font-bold text-yellow-700">{{ gpoName }}</div>
            <div class="mt-2 space-y-1.5 text-xs text-gray-500">
              <div v-if="sourceItemCodesDisplay">
                <span class="text-gray-400">Source:</span> <span class="font-mono font-semibold text-gray-700">{{ sourceItemCodesDisplay }}</span>
              </div>
              <div v-if="allSelectedBatches.length">
                <span class="text-gray-400">Batches:</span> {{ allSelectedBatches.length }} (qty {{ totalSourceQty }})
              </div>
              <div v-if="form.newItemCode">
                <span class="text-gray-400">Output:</span> <span class="font-mono font-semibold text-gray-700">{{ form.newItemCode }}</span>
              </div>
              <div v-if="poResult?.po_doc_num">
                <span class="text-gray-400">SAP PO#:</span> <span class="font-mono font-semibold text-blue-700">{{ poResult.po_doc_num }}</span>
              </div>
              <div v-if="completionResult">
                <span class="text-gray-400">GI:</span> <span class="font-mono text-green-700">{{ completionResult.goods_issue_doc }}</span>
              </div>
              <div v-if="completionResult">
                <span class="text-gray-400">GR:</span> <span class="font-mono text-green-700">{{ completionResult.goods_receipt_doc }}</span>
              </div>
            </div>
          </div>

          <!-- Total cost summary -->
          <div v-if="totalBatchCost > 0" class="bg-yellow-50 rounded-xl border border-yellow-200 p-4">
            <h3 class="text-xs font-semibold text-yellow-600 uppercase tracking-wide mb-2">Cost Summary</h3>
            <div class="text-lg font-bold text-yellow-800">₹{{ totalBatchCost.toFixed(2) }}</div>
            <div class="text-xs text-yellow-600 mt-0.5">Total GI cost</div>
            <div v-if="costSplit?.batch_cost" class="mt-2 text-xs text-yellow-700">
              <div v-for="line in (costSplit?.bom_lines || []).slice(0, 4)" :key="line.item_code" class="flex justify-between">
                <span class="font-mono truncate max-w-[100px]">{{ line.item_code }}</span>
                <span>₹{{ line.line_cost }}</span>
              </div>
            </div>
          </div>

          <!-- Back to dashboard -->
          <router-link
            to="/ghee-production-order"
            class="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 transition-colors px-1"
          >
            ← Dashboard
          </router-link>

        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { gheeProductionService } from '../services/gheeProductionService.js'

const steps = ['Select Source FG', 'BOM & Cost Split', 'Output Batches', 'Review & Create', 'Complete']
const currentStep = ref(1)
const error = ref('')

const form = reactive({
  newItemCode: '',
  docDate:     new Date().toISOString().slice(0, 10),
  remarks:     '',
})

// Each FG item: {item_code, loading, loaded, available_batches, batch_qtys}
// batch_qtys: { "BATCH|WHS": qty } — qty > 0 means selected; pre-filled on fetch
const sourceFGItems = ref([{
  item_code: '', loading: false, loaded: false,
  available_batches: [], batch_qtys: {},
}])

const outputBatchNos = ref({})
const costSplit      = ref(null)
const bomMessage      = ref('')
const editingBom      = ref(false)
const loadingBomSplit = ref(false)
const creatingPO      = ref(false)
const completing      = ref(false)
const poResult        = ref(null)
const completionResult = ref(null)
const gpoName         = ref(null)

// ── Section / dot helpers ──────────────────────────────────────────────────

function sectionClass(n) {
  return [
    'bg-white rounded-xl border shadow-sm p-6 transition-all',
    currentStep >= n ? 'border-gray-200' : 'border-dashed border-gray-200 bg-gray-50/50',
  ]
}

function stepDot(n) {
  return [
    'flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors',
    currentStep > n  ? 'bg-green-500 text-white' :
    currentStep === n ? 'bg-yellow-500 text-white' :
    'bg-gray-100 text-gray-400',
  ]
}

// ── GPO persistence ────────────────────────────────────────────────────────

async function saveOrder(extra = {}) {
  try {
    const srcCodes = sourceFGItems.value.filter(i => i.item_code.trim()).map(i => i.item_code)
    const res = await gheeProductionService.saveOrder({
      name:                   gpoName.value || undefined,
      current_step:           currentStep.value,
      source_item_code:       srcCodes.length === 1 ? srcCodes[0] : srcCodes.join(', '),
      new_item_code:          form.newItemCode,
      doc_date:               form.docDate,
      new_item_warehouse:     'HN-WIP',
      remarks:                form.remarks,
      selected_batches_json:  JSON.stringify(allSelectedBatches.value),
      output_batch_nos_json:  JSON.stringify(outputBatchNos.value),
      cost_split_json:        costSplit.value ? JSON.stringify(costSplit.value) : undefined,
      po_entry:               poResult.value?.po_entry   ?? undefined,
      po_doc_num:             poResult.value?.po_doc_num ?? undefined,
      ...extra,
    })
    if (res?.success) gpoName.value = res.name
  } catch (e) {
    console.warn('GPO save failed:', e.message)
  }
}

async function restoreOrder(order) {
  gpoName.value     = order.name
  currentStep.value = order.current_step || 1
  form.newItemCode  = order.new_item_code || ''
  form.docDate      = order.doc_date      || new Date().toISOString().slice(0, 10)
  form.remarks      = order.remarks       || ''

  if (order.selected_batches_json) {
    try {
      const flat = JSON.parse(order.selected_batches_json)
      // Group by item_code; reconstruct available_batches + batch_qtys from saved data
      const grouped = {}
      for (const sb of flat) {
        const ic = sb.item_code || order.source_item_code || ''
        if (!grouped[ic]) grouped[ic] = { batches: [], qtys: {} }
        grouped[ic].batches.push(sb.batch)
        grouped[ic].qtys[`${sb.batch.batch_number}|${sb.batch.warehouse}`] = sb.qty
      }
      sourceFGItems.value = Object.entries(grouped).map(([ic, g]) => ({
        item_code: ic, loading: false, loaded: true,
        available_batches: g.batches, batch_qtys: g.qtys,
      }))
      if (sourceFGItems.value.length === 0) sourceFGItems.value = [_emptyItem()]
    } catch {}
  }
  if (order.output_batch_nos_json) {
    try { outputBatchNos.value = JSON.parse(order.output_batch_nos_json) } catch {}
  }
  if (order.cost_split_json) {
    try { costSplit.value = JSON.parse(order.cost_split_json) } catch {}
  }
  if (order.po_entry) {
    poResult.value = { success: true, po_entry: order.po_entry, po_doc_num: order.po_doc_num }
  }
  if (order.goods_issue_doc) {
    completionResult.value = {
      goods_issue_doc:   order.goods_issue_doc,
      goods_receipt_doc: order.goods_receipt_doc,
      po_closed:         !!order.po_closed,
      cost_summary:      null,
    }
  }
}

const _route = useRoute()

onMounted(async () => {
  try {
    const gpoParam = _route.query?.gpo
    if (gpoParam) {
      const order = await gheeProductionService.getOrder(gpoParam)
      if (order) await restoreOrder(order)
    }
  } catch (e) {
    console.warn('Could not load GPO:', e.message)
  }
})

// ── Computed ───────────────────────────────────────────────────────────────

// Flat array of all selected batches (qty > 0) across all FG items
const allSelectedBatches = computed(() => {
  const result = []
  for (const item of sourceFGItems.value) {
    for (const b of item.available_batches) {
      const key = `${b.batch_number}|${b.warehouse}`
      const q   = Number(item.batch_qtys[key] || 0)
      if (q > 0) result.push({ item_code: item.item_code, batch: b, qty: q })
    }
  }
  return result
})

const totalSourceQty = computed(() => allSelectedBatches.value.reduce((s, sb) => s + sb.qty, 0))
const totalBatchCost = computed(() => allSelectedBatches.value.reduce((s, sb) => s + sb.qty * sb.batch.calc_price, 0))

const sourceItemCodesDisplay = computed(() =>
  sourceFGItems.value.filter(i => i.item_code.trim()).map(i => i.item_code).join(', ')
)

const allBatchNosEntered = computed(() => {
  if (!costSplit.value?.bom_lines?.length) return false
  return costSplit.value.bom_lines.every((l) => (outputBatchNos.value[l.item_code] || '').trim() !== '')
})

// ── Batch auto-fill ────────────────────────────────────────────────────────

// Live FG remainder recompute — batch_cost minus all non-FG line costs
const liveFgResidue = computed(() => {
  if (!costSplit.value) return 0
  const batchCost = Number(costSplit.value.batch_cost || 0)
  const nonFgCost = (costSplit.value.bom_lines || [])
    .filter(l => !l.is_fg)
    .reduce((s, l) => s + Number(l.quantity || 0) * Number(l.unit_price || 0), 0)
  return Math.max(batchCost - nonFgCost, 0)
})

const liveFgQty = computed(() => {
  if (!costSplit.value) return 0
  const fg = (costSplit.value.bom_lines || []).find(l => l.is_fg)
  return Number(fg?.quantity || 0)
})

function liveLineCost(line) {
  if (line.is_fg) return liveFgResidue.value.toFixed(3)
  return (Number(line.quantity || 0) * Number(line.unit_price || 0)).toFixed(3)
}

function liveUnitPrice(line) {
  if (line.is_fg) {
    const qty = liveFgQty.value
    return qty > 0 ? (liveFgResidue.value / qty).toFixed(3) : '0'
  }
  return line.unit_price
}

function saveBomEdits() {
  if (costSplit.value?.bom_lines) {
    for (const line of costSplit.value.bom_lines) {
      if (line.is_fg) {
        const qty = Number(line.quantity || 0)
        const residue = liveFgResidue.value
        line.line_cost  = residue.toFixed(3)
        line.unit_price = qty > 0 ? Number((residue / qty).toFixed(3)) : 0
      } else {
        line.line_cost = (Number(line.quantity || 0) * Number(line.unit_price || 0)).toFixed(3)
      }
    }
  }
  editingBom.value = false
}

function addBomRow() {
  if (!costSplit.value) return
  costSplit.value.bom_lines.push({
    item_code: '', item_name: '', quantity: 0, unit_price: 0, line_cost: '0', warehouse: 'HN-WIP', cost_source: 'manual',
  })
}

function removeBomRow(idx) {
  costSplit.value?.bom_lines?.splice(idx, 1)
}

// ── Multi-FG-item helpers ──────────────────────────────────────────────────

function _emptyItem() {
  return { item_code: '', loading: false, loaded: false, available_batches: [], batch_qtys: {} }
}

function addFGItem() { sourceFGItems.value.push(_emptyItem()) }

function removeFGItem(idx) {
  if (sourceFGItems.value.length > 1) sourceFGItems.value.splice(idx, 1)
}

async function fetchBatchesFor(idx) {
  const item = sourceFGItems.value[idx]
  if (!item.item_code.trim()) return
  item.loading          = true
  item.loaded           = false
  item.available_batches = []
  item.batch_qtys       = {}
  error.value           = ''
  try {
    const res = await gheeProductionService.getItemBatches(item.item_code.trim())
    if (res.success) {
      item.available_batches = res.data || []
      // Pre-fill qty = full available qty for every batch
      const qtys = {}
      for (const b of item.available_batches) {
        qtys[`${b.batch_number}|${b.warehouse}`] = b.quantity
      }
      item.batch_qtys = qtys
    } else {
      error.value = res.message || 'Failed to fetch batches.'
    }
    item.loaded = true
  } catch (e) {
    error.value = e.message || 'Failed to fetch batches.'
  } finally {
    item.loading = false
  }
}

// Per-item totals helpers — accept item object directly (no index lookup)
function itemSelectedQty(item) {
  if (!item?.available_batches) return 0
  return item.available_batches.reduce((s, b) => s + Number(item.batch_qtys?.[`${b.batch_number}|${b.warehouse}`] || 0), 0)
}
function itemSelectedCost(item) {
  if (!item?.available_batches) return 0
  return item.available_batches.reduce((s, b) => {
    const q = Number(item.batch_qtys?.[`${b.batch_number}|${b.warehouse}`] || 0)
    return s + q * (b.calc_price || 0)
  }, 0)
}
function batchQtyOver(item, b) {
  return Number(item.batch_qtys[`${b.batch_number}|${b.warehouse}`] || 0) > b.quantity
}

function selectAllBatchesFor(idx) {
  const item = sourceFGItems.value[idx]
  for (const b of item.available_batches) {
    item.batch_qtys[`${b.batch_number}|${b.warehouse}`] = b.quantity
  }
}
function clearAllBatchesFor(idx) {
  const item = sourceFGItems.value[idx]
  for (const b of item.available_batches) {
    item.batch_qtys[`${b.batch_number}|${b.warehouse}`] = 0
  }
}

function sourceBatchesPayload() {
  return JSON.stringify(allSelectedBatches.value.map(sb => ({
    item_code:  sb.item_code,
    batch_no:   sb.batch.batch_number,
    source_qty: sb.qty,
    warehouse:  sb.batch.warehouse,
  })))
}

// ── Step actions ───────────────────────────────────────────────────────────

async function step1Next() {
  if (!allSelectedBatches.value.length) return
  error.value = ''
  currentStep.value = 2
  await saveOrder()
}

async function fetchBomSplit() {
  if (!form.newItemCode.trim()) return
  loadingBomSplit.value = true
  costSplit.value      = null
  bomMessage.value     = ''
  editingBom.value     = false
  outputBatchNos.value = {}
  error.value          = ''
  try {
    const firstItemCode = sourceFGItems.value.find(i => i.item_code.trim())?.item_code || ''
    const res = await gheeProductionService.previewCostSplit(
      firstItemCode, null, form.newItemCode.trim(), null, null, sourceBatchesPayload(),
    )
    if (res.success) {
      costSplit.value = res
      if (!res.bom_lines || res.bom_lines.length === 0) {
        bomMessage.value = res.message || `No BOM found for "${form.newItemCode}" in SAP.`
      } else {
        await saveOrder()
      }
    } else {
      error.value = res.message || 'Failed to load BOM.'
    }
  } catch (e) {
    error.value = e.message || 'Unexpected error loading BOM.'
  } finally {
    loadingBomSplit.value = false
  }
}

async function goTo(n) {
  error.value = ''
  currentStep.value = n
  await saveOrder()
}

async function submitCreatePO() {
  creatingPO.value = true
  error.value      = ''
  if (!gpoName.value) await saveOrder({ status: 'Draft' })
  try {
    const firstItemCode = sourceFGItems.value.find(i => i.item_code.trim())?.item_code || ''
    const res = await gheeProductionService.createProductionOrder({
      source_item_code:   firstItemCode,
      source_batches:     sourceBatchesPayload(),
      new_item_code:      form.newItemCode,
      new_item_warehouse: 'HN-WIP',
      doc_date:           form.docDate,
      remarks:            form.remarks,
      gpo_name:           gpoName.value || undefined,
      bom_lines:          JSON.stringify(costSplit.value?.bom_lines || []),
    })
    if (res.success) {
      poResult.value    = res
      currentStep.value = 5
      await saveOrder({ po_entry: res.po_entry, po_doc_num: res.po_doc_num })
    } else {
      error.value = res.message || 'Failed to create Production Order.'
      await saveOrder({ error_message: res.message || 'PO create failed' })
    }
  } catch (e) {
    error.value = e.message || 'Unexpected error.'
    await saveOrder({ error_message: e.message || 'PO create error' })
  } finally {
    creatingPO.value = false
  }
}

async function submitComplete() {
  completing.value = true
  error.value      = ''
  try {
    const fgBatchNo = (outputBatchNos.value[form.newItemCode] || '').trim()
    const fgLine    = costSplit.value?.bom_lines?.find((l) => l.is_fg)
    const outputBatchesObj = {}
    for (const [code, batch] of Object.entries(outputBatchNos.value)) {
      if ((batch || '').trim()) outputBatchesObj[code] = batch.trim()
    }
    const firstItemCode = sourceFGItems.value.find(i => i.item_code.trim())?.item_code || ''
    const res = await gheeProductionService.completeProductionOrder({
      po_entry:           poResult.value.po_entry,
      po_doc_num:         poResult.value.po_doc_num,
      source_item_code:   firstItemCode,
      source_batches:     sourceBatchesPayload(),
      new_item_batch_no:  fgBatchNo || undefined,
      new_item_warehouse: fgLine?.warehouse || undefined,
      output_batches:     JSON.stringify(outputBatchesObj),
      doc_date:           form.docDate,
      gpo_name:           gpoName.value || undefined,
      bom_lines:          JSON.stringify(costSplit.value?.bom_lines || []),
    })
    if (res.success) {
      completionResult.value = res
    } else {
      error.value = res.message || 'Failed to complete production.'
    }
  } catch (e) {
    error.value = e.message || 'Unexpected error.'
  } finally {
    completing.value = false
  }
}

function resetForm() {
  gpoName.value = null
  Object.assign(form, {
    newItemCode: '',
    docDate:     new Date().toISOString().slice(0, 10),
    remarks:     '',
  })
  sourceFGItems.value = [_emptyItem()]
  outputBatchNos.value   = {}
  costSplit.value        = null
  bomMessage.value       = ''
  poResult.value         = null
  completionResult.value = null
  error.value            = ''
  currentStep.value      = 1
}
</script>
