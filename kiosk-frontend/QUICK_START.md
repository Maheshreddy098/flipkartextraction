# 🚀 Kiosk Frontend - Quick Start

## 📦 Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev
# Access: http://localhost:5173

# Build for production
npm run build
# Output: ../khanal_tech_integrations/public/kiosk/
```

---

## 🏗️ Architecture (Hybrid)

```
window.csrf_token → axios (58 files) + frappe-ui (3 files)
```

**Both read CSRF token automatically - No backend changes needed!**

---

## 🎯 Which API to Use?

### **Use axios (Existing Pattern):**
```javascript
import { malurGRNService } from '@/core/api/plants/malur/grnService'

const result = await malurGRNService.getGRNList()
```

### **Use frappe-ui (New Features):**
```javascript
import { createResource } from 'frappe-ui'

const data = createResource({
  url: 'khanal_tech_integrations.api.method_name',
  auto: false
})

await data.fetch()
```

---

## ✅ Pre-Commit Checklist

- [ ] No `console.log` added
- [ ] Build successful (`npm run build`)
- [ ] No new errors in console
- [ ] Tested locally

---

## 🔧 Common Tasks

### **Add a New API Endpoint:**

**Option 1: axios**
```javascript
// src/core/api/plants/malur/myService.js
import { BaseAPIService } from '@/core/api/common/baseService'

class MyService extends BaseAPIService {
  async fetchData() {
    return this.postPlantAPI('malur', 'my_module', 'my_method', {})
  }
}

export const myService = new MyService('MyService')
```

**Option 2: frappe-ui**
```javascript
// src/composables/useMyFeature.js
import { createResource } from 'frappe-ui'

export function useMyFeature() {
  return createResource({
    url: 'khanal_tech_integrations.api.my_endpoint'
  })
}
```

---

## 🐛 Debugging

### **CSRF Error?**
```javascript
// Check in browser console:
console.log('Token:', window.csrf_token)
// Should show a string, not undefined
```

### **Build Error?**
```bash
# Clear and reinstall
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## 📚 Documentation

- **Architecture:** `/KIOSK_API_ARCHITECTURE.md`
- **Production:** `/PRODUCTION_READY.md`
- **This File:** Quick reference

---

## 🎉 Status: **PRODUCTION READY**

All systems go! 🚀

