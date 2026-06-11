module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parser: "vue-eslint-parser",
  parserOptions: {
    parser: "@typescript-eslint/parser",
    ecmaVersion: "latest",
    sourceType: "module",
    extraFileExtensions: [".vue"],
  },
  extends: ["plugin:vue/vue3-essential"],
  rules: {
    "vue/multi-word-component-names": "off",
    "max-lines": ["warn", { max: 400, skipBlankLines: true, skipComments: true }],
    "max-lines-per-function": ["warn", { max: 150, skipBlankLines: true, skipComments: true }],
  },
};
