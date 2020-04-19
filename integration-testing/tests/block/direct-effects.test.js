/* eslint-env jest */

const cognito = require('../../utils/cognito.js')
const { mutations, queries } = require('../../schema')

const loginCache = new cognito.AppSyncLoginCache()

beforeAll(async () => {
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
})

beforeEach(async () => await loginCache.clean())
afterAll(async () => await loginCache.clean())


test('User.blockedUsers, User.blockedStatus respond correctly to blocking and unblocking', async () => {
  // us and them
  const [ourClient] = await loginCache.getCleanLogin()
  const [, theirUserId] = await loginCache.getCleanLogin()

  // verify we haven't blocked them
  let resp = await ourClient.query({query: queries.user, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['userId']).toBe(theirUserId)
  expect(resp['data']['user']['blockedStatus']).toBe('NOT_BLOCKING')

  resp = await ourClient.query({query: queries.self})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['blockedUsers']['items']).toHaveLength(0)

  // block them
  resp = await ourClient.mutate({mutation: mutations.blockUser, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['blockUser']['userId']).toBe(theirUserId)
  expect(resp['data']['blockUser']['blockedStatus']).toBe('BLOCKING')

  // verify that block shows up
  resp = await ourClient.query({query: queries.user, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['userId']).toBe(theirUserId)
  expect(resp['data']['user']['blockedStatus']).toBe('BLOCKING')

  resp = await ourClient.query({query: queries.self})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['blockedUsers']['items']).toHaveLength(1)
  expect(resp['data']['self']['blockedUsers']['items'][0]['userId']).toBe(theirUserId)

  // unblock them
  resp = await ourClient.mutate({mutation: mutations.unblockUser, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['unblockUser']['userId']).toBe(theirUserId)
  expect(resp['data']['unblockUser']['blockedStatus']).toBe('NOT_BLOCKING')

  // verify that block has disappeared
  resp = await ourClient.query({query: queries.user, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['userId']).toBe(theirUserId)
  expect(resp['data']['user']['blockedStatus']).toBe('NOT_BLOCKING')

  resp = await ourClient.query({query: queries.self})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['blockedUsers']['items']).toHaveLength(0)
})


test('Unblocking a user we have not blocked is an error', async () => {
  const [ourClient] = await loginCache.getCleanLogin()
  const [, theirUserId] = await loginCache.getCleanLogin()
  await expect(ourClient.mutate({mutation: mutations.unblockUser, variables: {userId: theirUserId}}))
    .rejects.toThrow(/ClientError: .* has not blocked /)
})


test('Double blocking a user is an error', async () => {
  const [ourClient] = await loginCache.getCleanLogin()
  const [, theirUserId] = await loginCache.getCleanLogin()

  // block them
  let resp = await ourClient.mutate({mutation: mutations.blockUser, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['blockUser']['userId']).toBe(theirUserId)

  // try to block them again
  await expect(ourClient.mutate({mutation: mutations.blockUser, variables: {userId: theirUserId}}))
    .rejects.toThrow(/ClientError: .* has already blocked /)
})


test('Trying to block or unblock yourself is an error', async () => {
  const [ourClient, ourUserId] = await loginCache.getCleanLogin()
  let variables = {userId: ourUserId}
  await expect(ourClient.mutate({mutation: mutations.blockUser, variables}))
    .rejects.toThrow(/ClientError: Cannot block yourself/)
  await expect(ourClient.mutate({mutation: mutations.unblockUser, variables}))
    .rejects.toThrow(/ClientError: Cannot unblock yourself/)
})


test('User.blockedUsers ordering, privacy', async () => {
  // us and two others
  const [ourClient, ourUserId] = await loginCache.getCleanLogin()
  const [other1Client, other1UserId] = await loginCache.getCleanLogin()
  const [, other2UserId] = await loginCache.getCleanLogin()

  // we block both of them
  let resp = await ourClient.mutate({mutation: mutations.blockUser, variables: {userId: other1UserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['blockUser']['userId']).toBe(other1UserId)

  resp = await ourClient.mutate({mutation: mutations.blockUser, variables: {userId: other2UserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['blockUser']['userId']).toBe(other2UserId)

  // check that they appear in the right order
  resp = await ourClient.query({query: queries.self})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['blockedUsers']['items']).toHaveLength(2)
  expect(resp['data']['self']['blockedUsers']['items'][0]['userId']).toBe(other2UserId)
  expect(resp['data']['self']['blockedUsers']['items'][1]['userId']).toBe(other1UserId)

  // check another user can't see our blocked users
  resp = await other1Client.query({query: queries.user, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['blockedUsers']).toBeNull()
})


test('We can block & unblock a user that has blocked us', async () => {
  // us and them
  const [ourClient, ourUserId] = await loginCache.getCleanLogin()
  const [theirClient, theirUserId] = await loginCache.getCleanLogin()

  // they block us
  let resp = await theirClient.mutate({mutation: mutations.blockUser, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['blockUser']['userId']).toBe(ourUserId)

  // verify we can still block them
  resp = await ourClient.mutate({mutation: mutations.blockUser, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['blockUser']['userId']).toBe(theirUserId)

  // verify we can still unblock them
  resp = await ourClient.mutate({mutation: mutations.unblockUser, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['unblockUser']['userId']).toBe(theirUserId)
})
