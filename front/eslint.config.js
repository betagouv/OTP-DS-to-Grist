import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import stylistic from '@stylistic/eslint-plugin'
import globals from 'globals'

export default [
  {
    ignores: ['dist/', 'coverage/']
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    plugins: { '@stylistic': stylistic },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        // Fonctions injectées par les pages Flask (static/js), hors bundle
        getGristContext: 'readonly',
        formatDate: 'readonly',
        apiFetch: 'readonly'
      }
    },
    rules: {
      // Correction
      'no-var': 'error',
      'prefer-const': 'error',
      'prefer-arrow-callback': 'warn',
      'no-unused-vars': 'warn',
      eqeqeq: ['error', 'always'],
      'no-console': ['warn', { allow: ['error', 'warn'] }],
      'no-debugger': 'error',
      'no-else-return': 'warn',
      'no-eq-null': 'warn',
      'no-unneeded-ternary': 'warn',
      'no-useless-return': 'warn',
      'no-warning-comments': 'warn',
      'prefer-destructuring': 'warn',

      // Style des templates : contenu d'un élément court laissé sur sa ligne
      'vue/singleline-html-element-content-newline': 'off',

      // Style : relais des anciennes règles de formatage d'ESLint
      '@stylistic/array-bracket-spacing': ['warn', 'never'],
      '@stylistic/brace-style': ['warn', '1tbs', { allowSingleLine: true }],
      '@stylistic/comma-spacing': 'warn',
      '@stylistic/computed-property-spacing': ['warn', 'never'],
      '@stylistic/function-call-argument-newline': ['warn', 'consistent'],
      '@stylistic/indent': ['warn', 2],
      '@stylistic/key-spacing': ['warn', { beforeColon: false, afterColon: true }],
      '@stylistic/max-len': ['warn', {
        code: 120,
        ignoreTrailingComments: true,
        ignoreStrings: true,
        ignoreTemplateLiterals: true,
        ignoreUrls: true
      }],
      '@stylistic/padding-line-between-statements': [
        'warn',
        { blankLine: 'always', prev: '*', next: 'return' }
      ],
      '@stylistic/newline-per-chained-call': 'warn',
      '@stylistic/no-mixed-spaces-and-tabs': 'warn',
      '@stylistic/no-multiple-empty-lines': 'warn',
      '@stylistic/no-tabs': 'warn',
      '@stylistic/no-trailing-spaces': 'warn',
      '@stylistic/quotes': ['warn', 'single', { avoidEscape: true }],
      '@stylistic/rest-spread-spacing': ['warn', 'never'],
      '@stylistic/semi-spacing': ['warn', { before: false, after: false }],
      '@stylistic/semi-style': ['warn', 'last']
    }
  },
  {
    // Configurations et tests s'exécutent sous Node (Vite, Vitest)
    files: ['*.config.js', 'vitest.setup.js', '**/__tests__/**'],
    languageOptions: { globals: globals.node }
  }
]
