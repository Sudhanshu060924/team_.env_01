import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

export default defineConfig([
  ...nextVitals,

  globalIgnores([
    ".next/**",
    "node_modules/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),

  {
    rules: {
      // Existing project code uses React's automatic JSX runtime.
      "no-undef": "off",

      // Existing components contain intentionally unused callback
      // parameters/props.
      "no-unused-vars": "off",

      // TypeScript ESLint handles these better than the base rule.
      "@typescript-eslint/no-unused-vars": "off",

      // Keep these as warnings instead of blocking production builds.
      "@next/next/no-img-element": "warn",
      "react-hooks/exhaustive-deps": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
]);
