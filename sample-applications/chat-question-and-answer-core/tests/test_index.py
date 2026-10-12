import json

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding


@pytest.fixture
def chain(mocker, tmp_path):
    # Imported lazily: app.config needs the dummy model config created by conftest.py.
    from app import chain as chain_module

    mocker.patch.object(chain_module, "vectorstore", None)
    mocker.patch.object(chain_module, "embedding", DeterministicFakeEmbedding(size=16))
    mocker.patch.object(chain_module.config, "INDEX_DIR", str(tmp_path / "index"))
    return chain_module


def ingest(chain, tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    assert chain.create_faiss_vectordb(file_path=path) is True


def restart(chain, mocker):
    mocker.patch.object(chain, "vectorstore", None)
    chain.load_index()


def test_index_survives_restart(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    ingest(chain, tmp_path, "b.txt", "beta " * 50)

    restart(chain, mocker)

    assert sorted(chain.get_document_from_vectordb()) == ["a.txt", "b.txt"]
    assert chain.vectorstore.similarity_search("alpha", k=1)


def test_delete_is_saved(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    ingest(chain, tmp_path, "b.txt", "beta " * 50)
    assert chain.delete_embedding_from_vectordb("a.txt") is True

    restart(chain, mocker)

    assert chain.get_document_from_vectordb() == ["b.txt"]


def test_delete_all_leaves_no_index(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    assert chain.delete_embedding_from_vectordb(delete_all=True) is True

    restart(chain, mocker)

    assert chain.vectorstore is None
    assert not list((tmp_path / "index").iterdir())


def test_changed_embedding_settings_drop_the_index(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    mocker.patch.object(chain.config, "EMBEDDING_MODEL_ID", "other/embedding-model")

    restart(chain, mocker)

    assert chain.vectorstore is None
    assert not list((tmp_path / "index").iterdir())


def test_embedding_device_does_not_drop_the_index(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    mocker.patch.object(chain.config, "EMBEDDING_DEVICE", "NPU")

    restart(chain, mocker)

    assert chain.get_document_from_vectordb() == ["a.txt"]


def test_missing_fingerprint_drops_the_index(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    (tmp_path / "index" / chain.FINGERPRINT_FILE).unlink()

    restart(chain, mocker)

    assert chain.vectorstore is None
    assert not (tmp_path / "index" / chain.INDEX_FILE).exists()


def test_corrupt_index_starts_empty(chain, mocker, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)
    (tmp_path / "index" / chain.INDEX_FILE).write_bytes(b"not an index")

    restart(chain, mocker)

    assert chain.vectorstore is None
    assert not list((tmp_path / "index").iterdir())


def test_fingerprint_is_written(chain, tmp_path):
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)

    saved = json.loads((tmp_path / "index" / chain.FINGERPRINT_FILE).read_text())

    assert saved == chain.index_fingerprint()


def test_no_index_dir_keeps_index_in_memory(chain, mocker, tmp_path):
    mocker.patch.object(chain.config, "INDEX_DIR", "")
    ingest(chain, tmp_path, "a.txt", "alpha " * 50)

    assert not (tmp_path / "index").exists()
    assert chain.get_document_from_vectordb() == ["a.txt"]
