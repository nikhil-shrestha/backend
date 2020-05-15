import base64
from os import path
from unittest.mock import Mock

from moto import mock_cognitoidp, mock_dynamodb2, mock_s3
import pytest

from app import clients, models

from app_tests.dynamodb.table_schema import table_schema

heic_path = path.join(path.dirname(__file__), 'fixtures', 'IMG_0265.HEIC')
grant_path = path.join(path.dirname(__file__), 'fixtures', 'grant.jpg')
tiny_path = path.join(path.dirname(__file__), 'fixtures', 'tiny.jpg')


@pytest.fixture
def image_data():
    with open(tiny_path, 'rb') as fh:
        yield fh.read()


@pytest.fixture
def image_data_b64(image_data):
    yield base64.b64encode(image_data)


@pytest.fixture
def grant_data():
    with open(grant_path, 'rb') as fh:
        yield fh.read()


@pytest.fixture
def grant_data_b64(grant_data):
    yield base64.b64encode(grant_data)


@pytest.fixture
def heic_data():
    with open(heic_path, 'rb') as fh:
        yield fh.read()


@pytest.fixture
def heic_data_b64(heic_data):
    yield base64.b64encode(heic_data)


@pytest.fixture
def appsync_client():
    yield Mock(clients.AppSyncClient(appsync_graphql_url='my-graphql-url'))


@pytest.fixture
def cloudfront_client():
    yield Mock(clients.CloudFrontClient(None, 'my-domain'))


@pytest.fixture
def mediaconvert_client():
    endpoint = 'https://my-media-convert-endpoint.com'
    yield Mock(clients.MediaConvertClient(
        endpoint=endpoint, aws_account_id='aws-aid', role_arn='role-arn', uploads_bucket='uploads-bucket'
    ))


@pytest.fixture
def post_verification_client():
    # by default, all images pass verification
    yield Mock(clients.PostVerificationClient(lambda: None), **{'verify_image.return_value': True})


@pytest.fixture
def cognito_client():
    with mock_cognitoidp():
        cognito_client = clients.CognitoClient('dummy', 'my-client-id')
        resp = cognito_client.boto_client.create_user_pool(
            PoolName='user-pool-name',
            AliasAttributes=['phone_number', 'email', 'preferred_username'],  # seems moto doesn't enforce uniqueness
        )
        cognito_client.user_pool_id = resp['UserPool']['Id']
        yield cognito_client


@pytest.fixture
def dynamo_client():
    with mock_dynamodb2():
        yield clients.DynamoClient(table_name='my-table', create_table_schema=table_schema)


@pytest.fixture
def facebook_client():
    yield Mock(clients.FacebookClient())


@pytest.fixture
def google_client():
    yield Mock(clients.GoogleClient(lambda: {}))


# can't nest the moto context managers, it appears. To be able to use two mocked S3 buckets
# they thus need to be yielded under the same context manager
@pytest.fixture
def s3_clients():
    with mock_s3():
        yield {
            'uploads': clients.S3Client(bucket_name='uploads-bucket', create_bucket=True),
            'placeholder-photos': clients.S3Client(bucket_name='placerholder-photos-bucket', create_bucket=True),
        }


@pytest.fixture
def s3_uploads_client(s3_clients):
    yield s3_clients['uploads']


@pytest.fixture
def s3_placeholder_photos_client(s3_clients):
    yield s3_clients['placeholder-photos']


@pytest.fixture
def album_manager(dynamo_client, s3_uploads_client, cloudfront_client):
    yield models.AlbumManager({
        'dynamo': dynamo_client,
        's3_uploads': s3_uploads_client,
        'cloudfront': cloudfront_client,
    })


@pytest.fixture
def block_manager(dynamo_client):
    yield models.BlockManager({'dynamo': dynamo_client})


@pytest.fixture
def chat_manager(dynamo_client, appsync_client):
    yield models.ChatManager({'appsync': appsync_client, 'dynamo': dynamo_client})


@pytest.fixture
def chat_message_manager(dynamo_client, appsync_client, cloudfront_client):
    yield models.ChatMessageManager({
        'appsync': appsync_client,
        'cloudfront': cloudfront_client,
        'dynamo': dynamo_client,
    })


@pytest.fixture
def comment_manager(dynamo_client, user_manager):
    yield models.CommentManager({'dynamo': dynamo_client}, managers={'user': user_manager})


@pytest.fixture
def feed_manager(dynamo_client):
    yield models.FeedManager({'dynamo': dynamo_client})


@pytest.fixture
def follow_manager(dynamo_client):
    yield models.FollowManager({'dynamo': dynamo_client})


@pytest.fixture
def ffs_manager(dynamo_client):
    yield models.FollowedFirstStoryManager({'dynamo': dynamo_client})


@pytest.fixture
def like_manager(dynamo_client):
    yield models.LikeManager({'dynamo': dynamo_client})


@pytest.fixture
def post_manager(appsync_client, dynamo_client, s3_uploads_client, cloudfront_client, post_verification_client):
    yield models.PostManager({
        'appsync': appsync_client,
        'dynamo': dynamo_client,
        's3_uploads': s3_uploads_client,
        'cloudfront': cloudfront_client,
        'post_verification': post_verification_client,
    })


@pytest.fixture
def trending_manager(dynamo_client):
    yield models.TrendingManager({'dynamo': dynamo_client})


@pytest.fixture
def user_manager(cloudfront_client, dynamo_client, s3_uploads_client, s3_placeholder_photos_client, cognito_client,
                 facebook_client, google_client):
    yield models.UserManager({
        'cloudfront': cloudfront_client,
        'dynamo': dynamo_client,
        's3_uploads': s3_uploads_client,
        's3_placeholder_photos': s3_placeholder_photos_client,
        'cognito': cognito_client,
        'facebook': facebook_client,
        'google': google_client,
    })


@pytest.fixture
def view_manager(dynamo_client):
    yield models.ViewManager({'appsync': appsync_client, 'dynamo': dynamo_client})