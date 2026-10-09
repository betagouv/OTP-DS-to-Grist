// Global setup for Jest tests

// Le front legacy (navigateur) appelle apiFetch global, fourni par static/js/apiClient.js.
// Sous Jest, on le relie au fetch mocké par chaque test.
global.apiFetch = (...args) => global.fetch(...args)

afterEach(() => {
  jest.useRealTimers()
  jest.clearAllMocks()
})
