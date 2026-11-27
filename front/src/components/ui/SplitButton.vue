<script setup>
// Bouton divisé : une action principale, et un bouton flèche qui déplie des
// actions secondaires. Accessibilité selon le modèle « disclosure » (bouton
// aria-expanded qui contrôle une liste de boutons), celui des menus du DSFR.
//
// La liste est positionnée en `fixed` sous le composant : un conteneur qui
// défile (contenu d'accordéon DSFR, `overflow-y: auto`) ne la rogne pas et ne
// grandit pas pour la contenir. Elle se referme si la page défile ou change de
// taille, plutôt que de suivre le composant.
import { ref, useId, onMounted, onBeforeUnmount } from 'vue'

defineOptions({ inheritAttrs: false })

defineProps({
  label: { type: String, required: true },
  // Nom accessible du bouton flèche, qui n'affiche qu'une icône
  toggleLabel: { type: String, required: true },
  // Actions secondaires : [{ label, value, icon }], icon étant une classe
  // d'icône DSFR facultative (ex. 'fr-icon-restart-line'), placée avant le texte
  actions: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
})

const emit = defineEmits(['click', 'action'])

const actionsId = useId()
const expanded = ref(false)
const root = ref(null)
const main = ref(null)
const toggle = ref(null)
const actionsPosition = ref({})

const open = () => {
  // Bords des deux boutons, et non du composant : dans un fr-btns-group, les
  // marges des boutons (côtés et dessous) agrandissent le composant
  const { left, bottom } = main.value.getBoundingClientRect()
  const { right } = toggle.value.getBoundingClientRect()
  actionsPosition.value = {
    top: `${bottom}px`,
    left: `${left}px`,
    minWidth: `${right - left}px`
  }
  expanded.value = true
}

const close = () => {
  expanded.value = false
}

const toggleActions = () => {
  if (expanded.value) close()
  else open()
}

const closeAndFocusToggle = () => {
  if (!expanded.value) return
  close()
  toggle.value?.focus()
}

const choose = (value) => {
  close()
  emit('action', value)
}

// Clic en dehors ou focus parti ailleurs (Tab) : la liste se referme
const closeOnOutsidePointer = (event) => {
  if (!root.value?.contains(event.target)) close()
}

const closeOnFocusLeaving = (event) => {
  if (event.relatedTarget && !root.value?.contains(event.relatedTarget)) close()
}

onMounted(() => {
  document.addEventListener('pointerdown', closeOnOutsidePointer)
  // Défilement de n'importe quel conteneur (capture), pas seulement de la page
  document.addEventListener('scroll', close, true)
  window.addEventListener('resize', close)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', closeOnOutsidePointer)
  document.removeEventListener('scroll', close, true)
  window.removeEventListener('resize', close)
})
</script>

<template>
  <div
    ref="root"
    class="split-button"
    @keydown.esc="closeAndFocusToggle"
    @focusout="closeOnFocusLeaving"
  >
    <button
      ref="main"
      v-bind="$attrs"
      type="button"
      class="fr-btn split-button__main"
      :disabled="disabled"
      @click="emit('click')"
    >
      {{ label }}
    </button>
    <button
      ref="toggle"
      type="button"
      class="fr-btn split-button__toggle"
      :title="toggleLabel"
      :aria-label="toggleLabel"
      :aria-expanded="String(expanded)"
      :aria-controls="actionsId"
      :disabled="disabled"
      @click="toggleActions"
    >
      <!-- Icône dans un span, et non en classe du bouton : dans un
           fr-btns-group--icon-left, le DSFR affiche le texte de tout bouton
           qui porte une classe d'icône -->
      <span
        :class="expanded ? 'fr-icon-arrow-up-s-line' : 'fr-icon-arrow-down-s-line'"
        aria-hidden="true"
      />
    </button>
    <ul
      v-show="expanded"
      :id="actionsId"
      class="split-button__actions"
      :style="actionsPosition"
    >
      <li
        v-for="action in actions"
        :key="action.value"
      >
        <button
          type="button"
          class="fr-btn fr-btn--secondary split-button__action"
          @click="choose(action.value)"
        >
          <!-- Icône dans un span, et non en classe du bouton : dans un
               fr-btns-group, le DSFR réduit à son icône tout bouton qui en
               porte une (texte masqué) -->
          <span
            v-if="action.icon"
            :class="[action.icon, 'fr-icon--sm', 'split-button__icon']"
            aria-hidden="true"
          />
          {{ action.label }}
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.split-button {
  display: inline-flex;
  /* Dans un fr-btns-group, ses enfants div prennent toute la largeur */
  width: auto;
}

/* Les deux boutons se touchent, même dans un fr-btns-group qui les espace */
.split-button .split-button__main {
  margin-right: 0;
}

.split-button .split-button__toggle {
  margin-left: 0;
  /* Séparateur entre les deux boutons, de la couleur de leur texte */
  border-left: 1px solid var(--text-inverted-blue-france);
  /* Largeur icône seule : sans classe d'icône sur le bouton (icône dans un
     span), un fr-btns-group--icon-left ne le réduit pas automatiquement */
  width: 2.5rem;
  justify-content: center;
}

.split-button__actions {
  position: fixed;
  z-index: 1000;
  margin: 0;
  padding: 0;
  list-style: none;
  background-color: var(--background-default-grey);
  box-shadow: 0 6px 18px 0 rgba(0, 0, 18, 0.16);
}

.split-button__actions li {
  padding: 0;
}

.split-button .split-button__action {
  width: 100%;
  margin: 0;
  white-space: nowrap;
}

.split-button__icon {
  margin-right: 0.5rem;
}
</style>
