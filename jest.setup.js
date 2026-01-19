// Global setup for Jest tests
afterEach(() => {
  jest.useRealTimers()
  jest.clearAllMocks()
})
