const js = require('@eslint/js')
const globals = require('globals')

module.exports = [
  {
    ignores: [
      'node_modules/',
      'static/js/socket.io.js',
      '.venv/',
      '**/*.min.js'
    ]
  },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'commonjs',
      globals: {
        ...globals.browser,
        ...globals.commonjs,
        ...globals.es2021,
        ...globals.jest
      }
    },
    rules: {
      'no-var': 'error',
      'prefer-const': 'error',
      'prefer-arrow-callback': 'warn',
      'no-unused-vars': 'warn',
      eqeqeq: ['error', 'always'],
      'no-console': ['warn', { allow: ['error', 'warn'] }],
      'no-debugger': 'error',
      'array-bracket-spacing': ['warn', 'never'],
      'brace-style': ['warn', '1tbs', { allowSingleLine: true }],
      'comma-spacing': 'warn',
      'computed-property-spacing': ['warn', 'never'],
      'function-call-argument-newline': ['warn', 'consistent'],
      indent: ['warn', 2],
      'jsx-quotes': ['warn', 'prefer-double'],
      'key-spacing': ['warn', { beforeColon: false, afterColon: true }],
      'max-len': ['warn', { ignoreTrailingComments: true }],
      'newline-before-return': 'warn',
      'newline-per-chained-call': 'warn',
      'no-else-return': 'warn',
      'no-eq-null': 'warn',
      'no-mixed-spaces-and-tabs': 'warn',
      'no-multiple-empty-lines': 'warn',
      'no-tabs': 'warn',
      'no-trailing-spaces': 'warn',
      'no-unneeded-ternary': 'warn',
      'no-useless-return': 'warn',
      'no-warning-comments': 'warn',
      'prefer-destructuring': 'warn',
      quotes: ['warn', 'single', { avoidEscape: true }],
      'rest-spread-spacing': ['warn', 'never'],
      'semi-spacing': ['warn', { before: false, after: false }],
      'semi-style': ['warn', 'last'],
    }
  }
]
