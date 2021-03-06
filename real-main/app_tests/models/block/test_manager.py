import uuid
from unittest import mock

import pytest

from app.models.block.exceptions import AlreadyBlocked, NotBlocked
from app.models.like.enums import LikeStatus
from app.models.post.enums import PostType


@pytest.fixture
def blocker_user(user_manager, cognito_client):
    user_id, username = str(uuid.uuid4()), str(uuid.uuid4())[:8]
    cognito_client.create_verified_user_pool_entry(user_id, username, f'{username}@real.app')
    yield user_manager.create_cognito_only_user(user_id, username)


blocked_user = blocker_user
blocker_user_2 = blocker_user
blocked_user_2 = blocker_user


def test_block_unfollows(block_manager, follower_manager, blocker_user, blocked_user):
    # mock out calls to the follow manager
    block_manager.follower_manager = mock.Mock(follower_manager)

    block_item = block_manager.block(blocker_user, blocked_user)
    assert block_item['blockerUserId'] == blocker_user.id
    assert block_item['blockedUserId'] == blocked_user.id

    # check it really is in the DB
    resp = block_manager.dynamo.get_block(blocker_user.id, blocked_user.id)
    assert resp is not None

    # check following manager was called to clear any followings
    assert block_manager.follower_manager.mock_calls == [
        mock.call.get_follow(blocker_user.id, blocked_user.id),
        mock.call.get_follow().unfollow(force=True),
        mock.call.get_follow(blocked_user.id, blocker_user.id),
        mock.call.get_follow().unfollow(force=True),
    ]


def test_block_clears_likes(block_manager, blocker_user, blocked_user, post_manager):
    blocker_post_id = 'blocker-post-id'
    blocked_post_id = 'blocked-post-id'

    # we each add a post
    blocker_post = post_manager.add_post(blocker_user, blocker_post_id, PostType.TEXT_ONLY, text='t')
    blocked_post = post_manager.add_post(blocked_user, blocked_post_id, PostType.TEXT_ONLY, text='t')

    # we each like each other's posts
    block_manager.like_manager.like_post(blocker_user, blocked_post, LikeStatus.ONYMOUSLY_LIKED)
    block_manager.like_manager.like_post(blocked_user, blocker_post, LikeStatus.ONYMOUSLY_LIKED)

    # check those likes are really there
    resp = block_manager.like_manager.get_like(blocker_user.id, blocked_post_id)
    assert resp.item['likeStatus'] == LikeStatus.ONYMOUSLY_LIKED
    resp = block_manager.like_manager.get_like(blocked_user.id, blocker_post_id)
    assert resp.item['likeStatus'] == LikeStatus.ONYMOUSLY_LIKED

    # do the blocking
    block_item = block_manager.block(blocker_user, blocked_user)
    assert block_item['blockerUserId'] == blocker_user.id
    assert block_item['blockedUserId'] == blocked_user.id

    # check those likes are no longer there
    assert block_manager.like_manager.get_like(blocker_user.id, blocked_post_id) is None
    assert block_manager.like_manager.get_like(blocked_user.id, blocker_post_id) is None


def test_block_deletes_direct_chat(block_manager, blocker_user, blocked_user, chat_manager):
    # add a direct chat between the two users
    chat_id = 'cid'
    chat_manager.add_direct_chat(chat_id, blocker_user.id, blocked_user.id)
    assert chat_manager.get_direct_chat(blocker_user.id, blocked_user.id)

    # do the blocking
    block_item = block_manager.block(blocker_user, blocked_user)
    assert block_item['blockerUserId'] == blocker_user.id
    assert block_item['blockedUserId'] == blocked_user.id

    # verify the direct chat has disappeared
    assert chat_manager.get_direct_chat(blocker_user.id, blocked_user.id) is None


def test_is_blocked(block_manager, blocker_user, blocked_user):
    # block then unblock, testing block state at every step
    assert block_manager.is_blocked(blocker_user.id, blocked_user.id) is False
    assert block_manager.block(blocker_user, blocked_user)
    assert block_manager.is_blocked(blocker_user.id, blocked_user.id) is True
    assert block_manager.unblock(blocker_user, blocked_user)
    assert block_manager.is_blocked(blocker_user.id, blocked_user.id) is False


def test_get_block_status(block_manager, blocker_user, blocked_user):
    assert block_manager.get_block_status(blocker_user.id, blocker_user.id) == 'SELF'
    assert block_manager.get_block_status(blocker_user.id, blocked_user.id) == 'NOT_BLOCKING'
    assert block_manager.block(blocker_user, blocked_user)
    assert block_manager.get_block_status(blocker_user.id, blocked_user.id) == 'BLOCKING'
    assert block_manager.unblock(blocker_user, blocked_user)
    assert block_manager.get_block_status(blocker_user.id, blocked_user.id) == 'NOT_BLOCKING'


def test_cant_double_block(block_manager, blocker_user, blocked_user):
    block_item = block_manager.block(blocker_user, blocked_user)
    assert block_item['blockerUserId'] == blocker_user.id
    assert block_item['blockedUserId'] == blocked_user.id

    with pytest.raises(AlreadyBlocked):
        block_manager.block(blocker_user, blocked_user)


def test_unblock(block_manager, blocker_user, blocked_user):
    # do the blocking
    block_item = block_manager.block(blocker_user, blocked_user)
    assert block_item['blockerUserId'] == blocker_user.id
    assert block_item['blockedUserId'] == blocked_user.id

    # unblock
    block_item = block_manager.unblock(blocker_user, blocked_user)
    assert block_item['blockerUserId'] == blocker_user.id
    assert block_item['blockedUserId'] == blocked_user.id

    # check the unblock really did clear the db
    resp = block_manager.dynamo.get_block(blocker_user.id, blocked_user.id)
    assert resp is None


def test_cant_unblock_if_not_blocked(block_manager, blocker_user, blocked_user):
    with pytest.raises(NotBlocked):
        block_manager.unblock(blocker_user, blocked_user)


def test_on_user_delete_unblock_all_blocks(block_manager, blocker_user, blocked_user, blocked_user_2):
    # blocker blocks both the blocked
    block_manager.block(blocker_user, blocked_user)
    block_manager.block(blocker_user, blocked_user_2)

    # blocked both block the blocker
    block_manager.block(blocked_user, blocker_user)
    block_manager.block(blocked_user_2, blocker_user)

    # check they really are in the DB
    assert block_manager.dynamo.get_block(blocker_user.id, blocked_user.id) is not None
    assert block_manager.dynamo.get_block(blocker_user.id, blocked_user_2.id) is not None
    assert block_manager.dynamo.get_block(blocked_user.id, blocker_user.id) is not None
    assert block_manager.dynamo.get_block(blocked_user_2.id, blocker_user.id) is not None

    # clear all our blocks
    block_manager.on_user_delete_unblock_all_blocks(blocker_user.id, old_item=blocker_user.item)

    # check they are no longer in the db
    assert block_manager.dynamo.get_block(blocker_user.id, blocked_user.id) is None
    assert block_manager.dynamo.get_block(blocker_user.id, blocked_user_2.id) is None
    assert block_manager.dynamo.get_block(blocked_user.id, blocker_user.id) is None
    assert block_manager.dynamo.get_block(blocked_user_2.id, blocker_user.id) is None
