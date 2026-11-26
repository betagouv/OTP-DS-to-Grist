// Absent de jsdom ; les suites en environnement node n'ont pas d'Element
if (typeof Element !== 'undefined' && typeof Element.prototype.scrollIntoView !== 'function') {
  Element.prototype.scrollIntoView = () => {}
}
