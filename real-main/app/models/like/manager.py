import logging

from app.models import block, follow, post, user

from . import enums, exceptions
from .dynamo import LikeDynamo
from .model import Like

logger = logging.getLogger()


class LikeManager:

    enums = enums
    exceptions = exceptions

    def __init__(self, clients, managers=None):
        managers = managers or {}
        managers['like'] = self
        self.block_manager = managers.get('block') or block.BlockManager(clients, managers=managers)
        self.follow_manager = managers.get('follow') or follow.FollowManager(clients, managers=managers)
        self.post_manager = managers.get('post') or post.PostManager(clients, managers=managers)
        self.user_manager = managers.get('user') or user.UserManager(clients, managers=managers)

        self.clients = clients
        if 'dynamo' in clients:
            self.dynamo = LikeDynamo(clients['dynamo'])
            self.post_dynamo = post.dynamo.PostDynamo(clients['dynamo'])

    def get_like(self, user_id, post_id):
        like_item = self.dynamo.get_like(user_id, post_id)
        return self.init_like(like_item) if like_item else None

    def init_like(self, like_item):
        return Like(like_item, self.clients)

    def like_post(self, user, post, like_status, now=None):
        posted_by_user = self.user_manager.get_user(post.posted_by_user_id)

        # can't like a post of a user that has blocked us
        if self.block_manager.is_blocked(posted_by_user.id, user.id):
            raise exceptions.LikeException(f'User has been blocked by owner of post `{post.id}`')

        # can't like a post of a user we have blocked
        if self.block_manager.is_blocked(user.id, posted_by_user.id):
            raise exceptions.LikeException(f'User has blocked owner of post `{post.id}`')

        # if the post is from a private user (other than ourselves) then we must be a follower to like the post
        if user.id != posted_by_user.id:
            if posted_by_user.item['privacyStatus'] != self.user_manager.enums.UserPrivacyStatus.PUBLIC:
                following = self.follow_manager.dynamo.get_following(user.id, posted_by_user.id)
                if not following or following['followStatus'] != self.follow_manager.enums.FollowStatus.FOLLOWING:
                    raise exceptions.LikeException(f'User does not have access to post `{post.id}`')

        required_status = self.post_manager.enums.PostStatus.COMPLETED
        if post.post_status != required_status:
            raise exceptions.LikeException(f'Can only like posts with {required_status} status')

        if post.item.get('likesDisabled'):
            raise exceptions.LikeException(f'Likes are disabled this post `{post.id}`')

        if posted_by_user.item.get('likesDisabled'):
            raise exceptions.LikeException(f'Owner of this post (user `{posted_by_user.id}` has disabled likes')

        user = self.user_manager.get_user(user.id)
        if user.item.get('likesDisabled'):
            raise exceptions.LikeException(f'Caller `{user.id}` has disabled likes')

        transacts = [
            self.dynamo.transact_add_like(user.id, post.item, like_status),
            self.post_dynamo.transact_increment_like_count(post.id, like_status),
        ]
        transact_exceptions = [
            self.exceptions.AlreadyLiked(user.id, post.id),
            post.exceptions.PostDoesNotExist(post.id),
        ]
        self.dynamo.client.transact_write_items(transacts, transact_exceptions)

        # increment the correct like counter on the in-memory copy of the post
        attr = 'onymousLikeCount' if like_status == enums.LikeStatus.ONYMOUSLY_LIKED else 'anonymousLikeCount'
        post.item[attr] = post.item.get(attr, 0) + 1

    def dislike_all_of_post(self, post_id):
        "Dislike all likes of a post"
        for like_item in self.dynamo.generate_of_post(post_id):
            self.init_like(like_item).dislike()

    def dislike_all_by_user(self, liked_by_user_id):
        "Dislike all likes by a user"
        for like_item in self.dynamo.generate_by_liked_by(liked_by_user_id):
            self.init_like(like_item).dislike()

    def dislike_all_by_user_from_user(self, liked_by_user_id, posted_by_user_id):
        "Dislike all likes by one user on posts from another user"
        for like_pk in self.dynamo.generate_pks_by_liked_by_for_posted_by(liked_by_user_id, posted_by_user_id):
            liked_by_user_id, post_id = self.dynamo.parse_pk(like_pk)
            self.get_like(liked_by_user_id, post_id).dislike()