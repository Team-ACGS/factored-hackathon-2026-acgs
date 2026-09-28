import type { MessageKey } from "../i18n/en";

const keys: Record<string, MessageKey> = {
  UsernameExistsException: "errors.userExists",
  NotAuthorizedException: "errors.wrongCredentials",
  UserNotFoundException: "errors.wrongCredentials",
  InvalidPasswordException: "errors.invalidPassword",
  CodeMismatchException: "errors.codeMismatch",
  ExpiredCodeException: "errors.codeExpired",
  LimitExceededException: "errors.tooManyAttempts",
  TooManyRequestsException: "errors.tooManyAttempts",
  TooManyFailedAttemptsException: "errors.tooManyAttempts",
};

export function authErrorKey(error: unknown): MessageKey {
  return (error instanceof Error && keys[error.name]) || "errors.generic";
}
