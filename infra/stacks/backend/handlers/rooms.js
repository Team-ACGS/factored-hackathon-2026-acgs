import { util } from '@aws-appsync/utils'

const STAFF_ISSUER = '${staff_issuer}'

export function onSubscribe(ctx) {
  if (ctx.identity.issuer === STAFF_ISSUER) {
    return
  }

  const customerId = ctx.info.channel.segments[1]

  if (!customerId || customerId !== ctx.identity.sub) {
    util.unauthorized()
  }
}
