from ade.ui import main as ui


def test_approval_reads_full_persisted_specification(workspace, monkeypatch):
    monkeypatch.setattr(ui, 'adi_manager', workspace)
    document = '# Specification\n' + ('Long requirement.\n' * 400) + '\n## Final criteria\nMust remain visible.'
    workspace.write_spec('product-1', document)
    record = ui.TaskRecord(id='document-test', task='test', workflow='dev_cycle', project_id='product-1')
    record.spec = document[:4000]
    assert ui._gate_document(record, 'spec') == document
    workspace.write_spec('product-1', document + '\nOwner revision')
    assert ui._gate_document(record, 'spec').endswith('Owner revision')


def test_approval_without_project_uses_complete_record():
    record = ui.TaskRecord(id='memory-document', task='test', workflow='dev_cycle')
    record.tz = 'x' * 6000
    record.spec = 'y' * 7000
    assert ui._gate_document(record, 'tz') == record.tz
    assert ui._gate_document(record, 'spec') == record.spec
    assert ui._gate_document(record, 'unknown') == ''
