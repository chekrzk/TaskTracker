(() => {
    'use strict';

    const board = document.querySelector('[data-kanban-board]');
    if (!board) {
        return;
    }

    const orderForm = document.getElementById('column-order-form');
    const inputContainer = document.getElementById('column-order-inputs');

    const refreshColumnButtons = () => {
        const columns = [...board.querySelectorAll('[data-column-id]')];
        columns.forEach((column, index) => {
            const left = column.querySelector('.js-column-left');
            const right = column.querySelector('.js-column-right');
            if (left) {
                left.disabled = index === 0;
            }
            if (right) {
                right.disabled = index === columns.length - 1;
            }
        });
    };

    if (orderForm && inputContainer) {
        board.addEventListener('click', (event) => {
            const button = event.target.closest(
                '.js-column-left, .js-column-right',
            );
            if (!button) {
                return;
            }

            const column = button.closest('[data-column-id]');
            if (button.classList.contains('js-column-left')) {
                const previous = column.previousElementSibling;
                if (previous) {
                    board.insertBefore(column, previous);
                }
            } else {
                const next = column.nextElementSibling;
                if (next) {
                    board.insertBefore(next, column);
                }
            }
            refreshColumnButtons();
        });

        orderForm.addEventListener('submit', () => {
            inputContainer.replaceChildren();
            board.querySelectorAll('[data-column-id]').forEach((column) => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'column_ids';
                input.value = column.dataset.columnId;
                inputContainer.appendChild(input);
            });
        });

        refreshColumnButtons();
    }

    if (board.dataset.canMoveTasks !== 'true' || !window.Sortable) {
        return;
    }

    const csrfToken = board.dataset.csrfToken;
    const sortables = [];

    const taskCards = (list) => (
        [...list.children].filter((item) => item.matches('.kanban-task'))
    );

    const syncColumn = (list) => {
        const cards = taskCards(list);
        const column = list.closest('[data-column-id]');
        const counter = column.querySelector('[data-column-count]');
        const emptyState = list.querySelector('[data-empty-column]');

        if (counter) {
            counter.textContent = cards.length;
        }
        if (cards.length === 0 && !emptyState) {
            const message = document.createElement('p');
            message.className = 'small text-secondary mb-0';
            message.dataset.emptyColumn = '';
            message.textContent = 'Задач нет.';
            list.appendChild(message);
        } else if (cards.length > 0 && emptyState) {
            emptyState.remove();
        }
    };

    const setDisabled = (disabled) => {
        sortables.forEach((sortable) => {
            sortable.option('disabled', disabled);
        });
    };

    board.querySelectorAll('[data-column-dropzone]').forEach((list) => {
        const sortable = window.Sortable.create(list, {
            group: 'team-tasks',
            animation: 150,
            draggable: '.kanban-task',
            sort: false,
            ghostClass: 'kanban-task-ghost',
            chosenClass: 'kanban-task-chosen',
            dragClass: 'kanban-task-drag',
            onAdd: async (event) => {
                const item = event.item;
                const source = event.from;
                const target = event.to;
                const oldIndex = (
                    event.oldDraggableIndex ?? event.oldIndex ?? 0
                );
                const targetColumn = target.closest('[data-column-id]');
                const columnId = Number(targetColumn.dataset.columnId);

                syncColumn(source);
                syncColumn(target);
                setDisabled(true);

                try {
                    const response = await fetch(item.dataset.moveUrl, {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken,
                            'Accept': 'application/json',
                        },
                        body: JSON.stringify({column_id: columnId}),
                    });
                    let payload = {};
                    try {
                        payload = await response.json();
                    } catch {
                        payload = {};
                    }
                    if (!response.ok || !payload.success) {
                        throw new Error(
                            payload.error || 'Не удалось переместить задачу.',
                        );
                    }
                } catch (error) {
                    const sourceCards = taskCards(source);
                    const reference = sourceCards[oldIndex] || null;
                    source.insertBefore(item, reference);
                    syncColumn(source);
                    syncColumn(target);
                    window.alert(
                        error.message || 'Не удалось переместить задачу.',
                    );
                } finally {
                    setDisabled(false);
                }
            },
        });
        sortables.push(sortable);
    });
})();
