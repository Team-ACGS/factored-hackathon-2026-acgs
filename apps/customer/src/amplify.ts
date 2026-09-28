import { Amplify } from "aws-amplify";

import { config } from "./config";

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: config.userPoolId,
      userPoolClientId: config.userPoolClientId,
      signUpVerificationMethod: "code",
      loginWith: { email: true },
    },
  },
  API: {
    Events: {
      endpoint: config.realtimeHttpUrl,
      region: config.region,
      defaultAuthMode: "userPool",
    },
  },
});
