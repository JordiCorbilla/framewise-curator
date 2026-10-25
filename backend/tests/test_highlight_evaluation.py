import pytest

from framewise.curation.evaluation import agreement


def records():
    predictions = [
        {
            "original_path": f"C:\\Trip\\{i}.NEF",
            "automatic_flickr": str(i == 0),
            "automatic_competition_rank": str(i + 1) if i < 3 else "",
            "competition_rank": "1" if i == 3 else "",
        }
        for i in range(4)
    ]
    labels = [
        {
            "original_path": row["original_path"],
            "flickr_favourite": str(i == 0),
            "competition_favourite": str(i in (0, 3)),
            "split": "heldout",
        }
        for i, row in enumerate(predictions)
    ]
    return predictions, labels


def test_evaluation_uses_automatic_rank_not_manual_replacement():
    predictions, labels = records()
    result = agreement(predictions, labels)
    assert result["flickr_precision"] == result["flickr_recall"] == 1
    assert result["competition_overlap_at3"] == 1
    assert result["competition_precision_at3"] == pytest.approx(1 / 3)
    assert result["competition_recall_at3"] == 0.5
    assert 0 < result["competition_ndcg_at3"] < 1


def test_evaluation_rejects_unlabelled_or_incomplete_universe():
    predictions, labels = records()
    with pytest.raises(ValueError, match="universe"):
        agreement(predictions, labels[:-1])
    labels[0]["flickr_favourite"] = ""
    with pytest.raises(ValueError, match="unlabelled"):
        agreement(predictions, labels)


def test_empty_recommendations_are_not_perfect_precision():
    predictions, labels = records()
    for row in predictions:
        row["automatic_flickr"], row["automatic_competition_rank"] = "false", ""
    result = agreement(predictions, labels)
    assert result["flickr_precision"] is None and result["competition_precision_at3"] is None
    assert result["flickr_recall"] == 0 and result["competition_ndcg_at3"] == 0
