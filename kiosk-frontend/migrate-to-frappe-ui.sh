#!/bin/bash

# Full frappe-ui Migration Script
# Converts all components from axios services to frappe-ui composables

set -e

echo "🚀 Starting Full Migration to frappe-ui..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter
total_files=0
migrated_files=0

# Function to migrate a file
migrate_file() {
  local file=$1
  local plant=$2
  local service_type=$3
  
  echo -e "${BLUE}Migrating: $file${NC}"
  
  # Backup
  cp "$file" "$file.backup-migration"
  
  # Replace imports based on service type
  if [ "$service_type" == "grn" ]; then
    sed -i '' "s/import { ${plant}GRNService } from.*grnService.*/import { useGRN } from '@\/composables\/useGRN'/g" "$file"
    sed -i '' "s/${plant}GRNService\./{ useGRN('${plant}') }/g" "$file" 
  elif [ "$service_type" == "production" ]; then
    sed -i '' "s/import.*productionService.*/import { useProduction } from '@\/composables\/useProduction'/g" "$file"
  elif [ "$service_type" == "inventory" ]; then
    sed -i '' "s/import.*inventoryService.*/import { useInventory } from '@\/composables\/useInventory'/g" "$file"
  fi
  
  ((migrated_files++))
  echo -e "${GREEN}✓ Migrated${NC}"
  echo ""
}

# Migrate Malur Plant
echo -e "${YELLOW}=== Migrating Malur Plant ===${NC}"
# Note: Manual migration needed for complex components
echo "⚠️  CreateGRNForm.vue needs manual migration (1800+ lines)"
echo ""

# Migrate Krishnagiri Plant
echo -e "${YELLOW}=== Migrating Krishnagiri Plant ===${NC}"
if [ -f "src/plants/krishnagiri/pages/GRN.vue" ]; then
  migrate_file "src/plants/krishnagiri/pages/GRN.vue" "krishnagiri" "grn"
fi

# Migrate Nandi Hills
echo -e "${YELLOW}=== Migrating Nandi Hills Plant ===${NC}"
if [ -f "src/plants/nandi-hills/pages/GRN.vue" ]; then
  migrate_file "src/plants/nandi-hills/pages/GRN.vue" "nandi_hills" "grn"
fi

# Migrate Mahadevpura
echo -e "${YELLOW}=== Migrating Mahadevpura Plant ===${NC}"
if [ -f "src/plants/mahadevpura/pages/GRN.vue" ]; then
  migrate_file "src/plants/mahadevpura/pages/GRN.vue" "mahadevpura" "grn"
fi

# Migrate Champavath
echo -e "${YELLOW}=== Migrating Champavath Plant ===${NC}"
if [ -f "src/plants/champavath/pages/GRN.vue" ]; then
  migrate_file "src/plants/champavath/pages/GRN.vue" "champavath" "grn"
fi

echo ""
echo -e "${GREEN}✓ Migration Complete!${NC}"
echo "Files migrated: $migrated_files"
echo ""
echo "⚠️  IMPORTANT: Large complex files need manual verification"
echo "Run: npm run build"
echo ""

