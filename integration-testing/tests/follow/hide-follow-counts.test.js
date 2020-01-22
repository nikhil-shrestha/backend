/* eslint-env jest */

const cognito = require('../../utils/cognito.js')
const schema = require('../../utils/schema.js')

const loginCache = new cognito.AppSyncLoginCache()

beforeAll(async () => {
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
})

beforeEach(async () => await loginCache.clean())
afterAll(async () => await loginCache.clean())


test('hideFollowCounts hides follow counts and followe[r|d]Users lists', async() => {
  const [ourClient, ourUserId] = await loginCache.getCleanLogin()
  const [theirClient, theirUserId] = await loginCache.getCleanLogin()

  // verify defaults
  let resp = await ourClient.query({query: schema.self})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['followCountsHidden']).toBe(false)
  expect(resp['data']['self']['followerCount']).toBe(0)
  expect(resp['data']['self']['followedCount']).toBe(0)
  resp = await ourClient.query({query: schema.ourFollowerUsers})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['followerUsers']['items']).toHaveLength(0)
  resp = await ourClient.query({query: schema.ourFollowedUsers})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['followedUsers']['items']).toHaveLength(0)

  // they follow us, we follow them
  resp = await ourClient.mutate({mutation: schema.followUser, variables: {userId: theirUserId}})
  expect(resp['errors']).toBeUndefined()
  resp = await theirClient.mutate({mutation: schema.followUser, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()

  // check our followCountsHidden state, and our follow counts, other user can't see our setting
  resp = await theirClient.query({query: schema.user, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followCountsHidden']).toBeNull()
  expect(resp['data']['user']['followerCount']).toBe(1)
  expect(resp['data']['user']['followedCount']).toBe(1)
  resp = await theirClient.query({query: schema.followerUsers, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followerUsers']['items']).toHaveLength(1)
  expect(resp['data']['user']['followerUsers']['items'][0]['userId']).toBe(theirUserId)
  resp = await theirClient.query({query: schema.followedUsers, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followedUsers']['items']).toHaveLength(1)
  expect(resp['data']['user']['followedUsers']['items'][0]['userId']).toBe(theirUserId)

  // hide our follow counts
  resp = await ourClient.mutate({mutation: schema.setUserFollowCountsHidden, variables: {value: true}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['setUserDetails']['followCountsHidden']).toBe(true)

  // verify those counts are no longer visible by the other user
  resp = await theirClient.query({query: schema.user, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followCountsHidden']).toBeNull()
  expect(resp['data']['user']['followerCount']).toBeNull()
  expect(resp['data']['user']['followedCount']).toBeNull()
  resp = await theirClient.query({query: schema.followerUsers, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followerUsers']).toBeNull()
  resp = await theirClient.query({query: schema.followedUsers, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followedUsers']).toBeNull()

  // verify we can still see our own counts
  // TODO: should we be able to see this? Or is this a hide-it-from-yourself setting?
  resp = await ourClient.query({query: schema.self})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['followCountsHidden']).toBe(true)
  expect(resp['data']['self']['followerCount']).toBe(1)
  expect(resp['data']['self']['followedCount']).toBe(1)
  resp = await ourClient.query({query: schema.ourFollowerUsers})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['followerUsers']['items']).toHaveLength(1)
  expect(resp['data']['self']['followerUsers']['items'][0]['userId']).toBe(theirUserId)
  resp = await ourClient.query({query: schema.ourFollowedUsers})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['self']['followedUsers']['items']).toHaveLength(1)
  expect(resp['data']['self']['followedUsers']['items'][0]['userId']).toBe(theirUserId)

  // reveal our follow counts
  resp = await ourClient.mutate({mutation: schema.setUserFollowCountsHidden, variables: {value: false}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['setUserDetails']['followCountsHidden']).toBe(false)

  // verify the other user can again see those counts
  resp = await theirClient.query({query: schema.user, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followCountsHidden']).toBeNull()
  expect(resp['data']['user']['followerCount']).toBe(1)
  expect(resp['data']['user']['followedCount']).toBe(1)
  resp = await theirClient.query({query: schema.followerUsers, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followerUsers']['items']).toHaveLength(1)
  expect(resp['data']['user']['followerUsers']['items'][0]['userId']).toBe(theirUserId)
  resp = await theirClient.query({query: schema.followedUsers, variables: {userId: ourUserId}})
  expect(resp['errors']).toBeUndefined()
  expect(resp['data']['user']['followedUsers']['items']).toHaveLength(1)
  expect(resp['data']['user']['followedUsers']['items'][0]['userId']).toBe(theirUserId)
})