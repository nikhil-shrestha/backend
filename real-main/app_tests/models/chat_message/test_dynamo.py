import pendulum
import pytest

from app.models.chat_message.dynamo import ChatMessageDynamo


@pytest.fixture
def chat_message_dynamo(dynamo_client):
    yield ChatMessageDynamo(dynamo_client)


@pytest.mark.parametrize('user_id', ['uid', None])
def test_add_chat_message(chat_message_dynamo, user_id):
    message_id = 'mid'
    chat_id = 'cid'
    text = 'message_text'
    text_tags = [
        {'tag': '@1', 'userId': 'uidt1'},
        {'tag': '@2', 'userId': 'uidt2'},
    ]

    now = pendulum.now('utc')
    expected_item = {
        'partitionKey': 'chatMessage/mid',
        'sortKey': '-',
        'schemaVersion': 1,
        'gsiA1PartitionKey': 'chatMessage/cid',
        'gsiA1SortKey': now.to_iso8601_string(),
        'messageId': 'mid',
        'chatId': 'cid',
        'createdAt': now.to_iso8601_string(),
        'text': text,
        'textTags': text_tags,
    }
    if user_id:
        expected_item['userId'] = user_id

    # add the chat to the DB, verify correct form
    item = chat_message_dynamo.add_chat_message(message_id, chat_id, user_id, text, text_tags, now)
    assert item == expected_item
    assert item == chat_message_dynamo.get_chat_message(message_id)

    # verify we can't add the same message twice
    with pytest.raises(chat_message_dynamo.client.exceptions.ConditionalCheckFailedException):
        chat_message_dynamo.add_chat_message(message_id, chat_id, user_id, text, text_tags, now)


def test_edit_chat_message(chat_message_dynamo):
    message_id = 'mid'
    new_text = 'new message_text'
    new_text_tags = [
        {'tag': '@4', 'userId': 'uidt6'},
    ]
    edited_at = pendulum.now('utc')

    # verify we can't edit message that doesn't exist
    with pytest.raises(chat_message_dynamo.client.exceptions.ConditionalCheckFailedException):
        chat_message_dynamo.edit_chat_message(message_id, new_text, new_text_tags, edited_at)

    # add the message
    chat_id = 'cid'
    user_id = 'uid'
    org_text = 'message_text'
    org_text_tags = [
        {'tag': '@1', 'userId': 'uidt1'},
        {'tag': '@2', 'userId': 'uidt2'},
    ]
    added_at = pendulum.now('utc')

    # add the message to the DB
    item = chat_message_dynamo.add_chat_message(message_id, chat_id, user_id, org_text, org_text_tags, added_at)
    assert item['messageId'] == 'mid'
    assert item['text'] == org_text
    assert item['textTags'] == org_text_tags
    assert 'lastEditedAt' not in item

    # edit the message
    new_item = chat_message_dynamo.edit_chat_message(message_id, new_text, new_text_tags, edited_at)
    assert new_item == chat_message_dynamo.get_chat_message(message_id)
    assert new_item['messageId'] == 'mid'
    assert new_item['text'] == new_text
    assert new_item['textTags'] == new_text_tags
    assert pendulum.parse(new_item['lastEditedAt']) == edited_at
    item['text'] = new_item['text']
    item['textTags'] = new_item['textTags']
    item['lastEditedAt'] = new_item['lastEditedAt']
    assert new_item == item


def test_delete_chat_message(chat_message_dynamo):
    message_id = 'mid'

    # add the message to the DB
    now = pendulum.now('utc')
    item = chat_message_dynamo.add_chat_message(message_id, 'cid', 'uid', 'lore ipsum', [], now)
    assert item['messageId'] == 'mid'

    # delete the message
    new_item = chat_message_dynamo.delete_chat_message(message_id)
    assert new_item == item
    assert chat_message_dynamo.get_chat_message(message_id) is None

    # verify idempotent
    new_item = chat_message_dynamo.delete_chat_message(message_id)
    assert new_item is None
    assert chat_message_dynamo.get_chat_message(message_id) is None


def test_generate_chat_messages_by_chat(chat_message_dynamo):
    chat_id = 'cid'

    # verify with no chat messages / chat doesn't exist
    assert list(chat_message_dynamo.generate_chat_messages_by_chat(chat_id)) == []
    assert list(chat_message_dynamo.generate_chat_messages_by_chat(chat_id, pks_only=True)) == []

    # add a chat message
    message_id_1 = 'mid1'
    now = pendulum.now('utc')
    chat_message_dynamo.add_chat_message(message_id_1, chat_id, 'uid', 'lore', [], now)

    # verify with one chat message
    items = list(chat_message_dynamo.generate_chat_messages_by_chat(chat_id))
    assert len(items) == 1
    assert items[0]['messageId'] == message_id_1

    pks = list(chat_message_dynamo.generate_chat_messages_by_chat(chat_id, pks_only=True))
    assert len(pks) == 1
    assert pks[0] == {'partitionKey': 'chatMessage/mid1', 'sortKey': '-'}

    # add another chat message
    message_id_2 = 'mid2'
    now = pendulum.now('utc')
    chat_message_dynamo.add_chat_message(message_id_2, chat_id, 'uid', 'ipsum', [], now)

    # verify with two chat messages
    items = list(chat_message_dynamo.generate_chat_messages_by_chat(chat_id))
    assert len(items) == 2
    assert items[0]['messageId'] == message_id_1
    assert items[1]['messageId'] == message_id_2

    pks = list(chat_message_dynamo.generate_chat_messages_by_chat(chat_id, pks_only=True))
    assert len(pks) == 2
    assert pks[0] == {'partitionKey': 'chatMessage/mid1', 'sortKey': '-'}
    assert pks[1] == {'partitionKey': 'chatMessage/mid2', 'sortKey': '-'}
