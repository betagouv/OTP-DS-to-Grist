import { describe, it, expect, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'

import SplitButton from '../SplitButton.vue'

const ACTIONS = [{ label: 'Action secondaire', value: 'secondaire' }]

const mountSplitButton = (props = {}) => mount(SplitButton, {
  props: { label: 'Action principale', toggleLabel: 'Autres actions', actions: ACTIONS, ...props },
  attrs: { 'data-test-id': 'main' },
  attachTo: document.body
})

const toggleOf = (wrapper) => wrapper.find('[aria-controls]')
const actionsOf = (wrapper) => wrapper.find('ul')

describe('SplitButton', () => {
  let wrapper

  afterEach(() => {
    wrapper.unmount()
  })

  it('emits click from the main button, which receives the attributes', async () => {
    wrapper = mountSplitButton()

    await wrapper.find('[data-test-id="main"]').trigger('click')

    expect(wrapper.emitted('click')).toHaveLength(1)
    expect(wrapper.find('[data-test-id="main"]').text()).toBe('Action principale')
  })

  it('toggle has an accessible name and controls the hidden actions list', () => {
    wrapper = mountSplitButton()
    const toggle = toggleOf(wrapper)

    expect(toggle.text()).toBe('Autres actions')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.attributes('aria-controls')).toBe(actionsOf(wrapper).attributes('id'))
    expect(actionsOf(wrapper).isVisible()).toBe(false)
  })

  it('toggle shows then hides the actions', async () => {
    wrapper = mountSplitButton()

    await toggleOf(wrapper).trigger('click')
    expect(toggleOf(wrapper).attributes('aria-expanded')).toBe('true')
    expect(actionsOf(wrapper).isVisible()).toBe(true)

    await toggleOf(wrapper).trigger('click')
    expect(toggleOf(wrapper).attributes('aria-expanded')).toBe('false')
  })

  it('choosing an action emits its value and closes the list', async () => {
    wrapper = mountSplitButton()
    await toggleOf(wrapper).trigger('click')

    await actionsOf(wrapper).find('button')
      .trigger('click')

    expect(wrapper.emitted('action')).toEqual([['secondaire']])
    expect(wrapper.emitted('click')).toBeUndefined()
    expect(actionsOf(wrapper).isVisible()).toBe(false)
  })

  it('Escape closes the list and gives focus back to the toggle', async () => {
    wrapper = mountSplitButton()
    await toggleOf(wrapper).trigger('click')
    actionsOf(wrapper).find('button').element.focus()

    await actionsOf(wrapper).find('button')
      .trigger('keydown', { key: 'Escape' })

    expect(actionsOf(wrapper).isVisible()).toBe(false)
    expect(document.activeElement).toBe(toggleOf(wrapper).element)
  })

  it('pointer outside closes the list', async () => {
    wrapper = mountSplitButton()
    await toggleOf(wrapper).trigger('click')

    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await wrapper.vm.$nextTick()

    expect(actionsOf(wrapper).isVisible()).toBe(false)
  })

  it('focus leaving the component closes the list', async () => {
    wrapper = mountSplitButton()
    await toggleOf(wrapper).trigger('click')
    const outside = document.createElement('button')
    document.body.appendChild(outside)

    await toggleOf(wrapper).trigger('focusout', { relatedTarget: outside })

    expect(actionsOf(wrapper).isVisible()).toBe(false)
    outside.remove()
  })

  it('opens the list fixed right under both buttons, as wide as them', async () => {
    wrapper = mountSplitButton()
    // Le composant est plus grand que ses boutons (marges du fr-btns-group)
    wrapper.element.getBoundingClientRect = () => ({ bottom: 136, left: 22, right: 278 })
    wrapper.find('[data-test-id="main"]').element.getBoundingClientRect = () => (
      { bottom: 120, left: 30, right: 230 }
    )
    toggleOf(wrapper).element.getBoundingClientRect = () => (
      { bottom: 120, left: 230, right: 270 }
    )

    await toggleOf(wrapper).trigger('click')

    const {style} = actionsOf(wrapper).element
    expect(style.top).toBe('120px')
    expect(style.left).toBe('30px')
    expect(style.minWidth).toBe('240px')
  })

  it('scrolling closes the list', async () => {
    wrapper = mountSplitButton()
    await toggleOf(wrapper).trigger('click')

    document.body.dispatchEvent(new Event('scroll'))
    await wrapper.vm.$nextTick()

    expect(actionsOf(wrapper).isVisible()).toBe(false)
  })

  it('shows the icon given for an action, before its text', () => {
    wrapper = mountSplitButton({
      actions: [{ label: 'Avec icône', value: 'icone', icon: 'fr-icon-restart-line' }, ...ACTIONS]
    })
    const [withIcon, withoutIcon] = actionsOf(wrapper).findAll('button')

    // Icône dans un span décoratif : le bouton lui-même ne porte pas de
    // classe d'icône, qui le réduirait à son icône dans un fr-btns-group
    const icon = withIcon.find('span')
    expect(icon.classes()).toContain('fr-icon-restart-line')
    expect(icon.attributes('aria-hidden')).toBe('true')
    expect(withIcon.classes().some((name) => name.startsWith('fr-icon-'))).toBe(false)
    expect(withIcon.text()).toBe('Avec icône')
    expect(withoutIcon.find('span').exists()).toBe(false)
  })

  it('disabled disables both buttons', () => {
    wrapper = mountSplitButton({ disabled: true })

    expect(wrapper.find('[data-test-id="main"]').attributes('disabled')).toBeDefined()
    expect(toggleOf(wrapper).attributes('disabled')).toBeDefined()
  })
})
