import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            { name: "amplify", test: /node_modules[\\/].*(aws-amplify|@aws-amplify|@aws-crypto|@aws-sdk|@smithy)/ },
            { name: "react", test: /node_modules[\\/].*(react|react-dom|scheduler|@tanstack)[\\/]/ },
          ],
        },
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
