<script setup>
import { ref, onMounted } from 'vue'

import {
  DsfrAccordion,
  DsfrAccordionsGroup,
  DsfrInputGroup
} from '@gouvminint/vue-dsfr'

// TODO le mettre dans le parent
const activeAccordion = ref(0) // Premier accordéon ouvert par défaut
const accordionTitleDN = ref('Configurer votre démarche')
</script>

<template>
  <h3 class="fr-mb-3w">2. Démarche numérique</h3>

  <DsfrAccordionsGroup v-model="activeAccordion">
    <DsfrAccordion
      id="accordion-dn"
      :title="accordionTitleDN"
    >
      <DsfrInputGroup
        :error-message="WIP"
        data-test-id="dn-token"
        v-model="inputDNToken"
        @change="handleDNInputChange"
        label="DN token"
        placeholder="xxx"
        required
      />
    </DsfrAccordion>
  </DsfrAccordionsGroup>
</template>
