from Helpers.OrderingStage import Order
from Helpers.Data import menu, stores
from openpyxl import load_workbook, workbook
from telegram.ext import (Updater, CommandHandler, CallbackQueryHandler, CallbackContext, ConversationHandler, 
    MessageHandler, Filters, PollAnswerHandler, PollHandler)
from telegram import (ParseMode, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, 
    ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.utils.helpers import mention_html

sub_1, sub_2, sub_3, sub_4 = range(4)

def LetsMakan(update, context):
    # Check where the message is coming from
    if (update.effective_message.chat.type != "group"):
        context.bot.sendMessage(update.effective_user.id, text = "Send your commands in a group")
        return ConversationHandler.END

    # Check if group has already placed an order
    if update.effective_message.chat.id in context.bot_data:
        context.bot.sendMessage(update.effective_user.id, text = "Eh bro, already got one makan session. Either /EndMakan or /CancelMakan before making another session.")
        return ConversationHandler.END
    
    # Check for available restaurants
    available_restaurants = []
    for id in stores.toList("ID"):
        if context.bot_data[id]['Store Open']:
            available_restaurants.append(stores.stores(id))

    # prompt user to choose a restaurant
    # available_restaurants = menu.rests()
    if not available_restaurants:
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Sorry, there aren't any restaurants available at this time")
        return ConversationHandler.END
    else:
        buttons = [[InlineKeyboardButton(r, callback_data=r)] for r in available_restaurants]
        reply_markup = InlineKeyboardMarkup(buttons)
        context.bot.sendMessage(chat_id = update.effective_user.id, text = "Please select a restaurant:\nPress /cancel to cancel request ", reply_markup = reply_markup)

        context.user_data["chat_id"] = update.effective_chat.id
        return sub_1

def LetsMakan_helper(update, context):
    restaurant = update.callback_query.data

    # Delete message
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    # Create order object
    new_order = Order(update.effective_user, restaurant = restaurant)
    context.bot_data[context.user_data["chat_id"]] = new_order

    # Prompt user to start ordering!
    context.bot.sendMessage(chat_id = context.user_data["chat_id"], text = 
        new_order.restaurant + " is chosen! Use the following commands: " + 
        "\n/addOrder - add order" + 
        "\n/viewOrder - view all orders" + 
        "\n/removeOrder - remove an order" +
        "\n/EndMakan - EndMakan"
        "\n/CancelMakan - Cancel Makan")

    return ConversationHandler.END

def CancelMakan(update, context):
    # Accept only commands from group chat
    if messageError(update, context):
        return ConversationHandler.END

    # Only Host can close Makan
    if context.bot_data[update.effective_chat.id].user.id != update.effective_user.id:
        # End Convo
        user = context.bot_data[update.effective_chat.id].user.full_name
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Wah dun anyhow cancel leh?\nPlease ask {}".format(user))
        return

    del context.bot_data[update.effective_chat.id]
    context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Makan Session has been cancelled, boss")

def EndMakan(update, context):
    # Accept only commands from group chat
    if messageError(update, context):
        return ConversationHandler.END
    
    # Only Host can close Makan
    if context.bot_data[update.effective_chat.id].user.id != update.effective_user.id:
        # End Convo
        user = context.bot_data[update.effective_chat.id].user.full_name
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Eh hu give u the mandate the close the makan?\nPlease ask {}".format(user))
        return ConversationHandler.END
    
    order = context.bot_data[update.effective_chat.id]
    if not context.bot_data[stores.ID(order.restaurant)]['Store Open']:
        # If store is not open, then cancel order and apologise
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Wah u suay sia, the store just closed man... Press /Poll or /LetsMakan to see which restaurants are available")
        del context.bot_data[update.effective_chat.id]

        return ConversationHandler.END

    # Check if user has ordered anything
    elif not order.food:
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Oi recruit, ur order is empty leh. Dun anyhow play can anot?!")
        
        return ConversationHandler.END

    elif order.totalCost()<2:
        
        context.bot.sendMessage(chat_id = update.effective_chat.id, 
            text = ("You order is less than the minumum cost\nCurrent total cost: ${:.2f}\nMin order: $2").format(order.totalCost()))
            
        return ConversationHandler.END

    else:
        # Ask user to confirm
        buttons = [["Confirm plus chop"], ["Hol up"]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard= True)
        context.bot.sendMessage(update.effective_user.id, text = "Please confirm your order:\n{}".format(order.printOrder()), reply_markup = reply_markup)

        # Add user to botdata   
        context.user_data["chat_id"] = update.effective_chat.id
        return sub_1

def EndMakan_helper(update, context):
    if update.effective_message.text == "Confirm plus chop" :
        return Phone(update, context)
    else:
        # End convo tell user to continue ordering
        context.bot.sendMessage(chat_id = update.effective_user.id, text = "Okay, continue ordering... take ur time recruit",
            reply_markup = ReplyKeyboardRemove())
        return ConversationHandler.END

def Phone(update, context):
    # Prompt user to Key in phone number
    text = "Please key in your phone number: " if update.effective_message.text == "Confirm plus chop" else "Please key in a valid 8 digit number"
    context.bot.sendMessage(chat_id = update.effective_user.id, text = text, 
        reply_markup = ReplyKeyboardRemove())
    return sub_2

def save_phone(update, context):
    # Check if number is valid
    num = update.effective_message.text
    if len(num) == 8 and (num[0] == '9' or num[0] == '8' or num[0] == '6'):
        order = context.bot_data[context.user_data["chat_id"]]
        order.phone = update.effective_message.text

        return address(update, context)
        
    else:
        # Invalid Number
        context.bot.sendMessage(chat_id = update.effective_user.id, text = "Invalid number")
        return Phone(update, context)

def address(update, context):
    list_of_residence = ["Eusoff Hall", "Kent Ridge Hall", "King Edward VII Hall", "Raffles Hall", "Sheares Hall", "Temasek Hall", "PGP House", "CAPT", "Tembusu", "RVRC", "RC4", "Cinnamon"]
    buttons = [InlineKeyboardButton(h, callback_data=h) for h in list_of_residence]
    format_buttons = [buttons[0:2], buttons[2:4], buttons[4:6], buttons[6:8], buttons[8:10], buttons[10:12]]
    reply_markup = InlineKeyboardMarkup(format_buttons)
    # Prompt user to key in address
    context.bot.sendMessage(chat_id = update.effective_user.id, text = "Please key in your address details: ", reply_markup = reply_markup)
    return sub_3

def save_address(update, context):
    # save address
    order = context.bot_data[context.user_data["chat_id"]] 
    order.address = update.callback_query.data
    
    # Add order to queue
    return addToQueue(update,context)

def addToQueue(update, context):
    # Add to Store's Queue
    order = context.bot_data[context.user_data["chat_id"]] 
    store = context.bot_data[stores.ID(order.restaurant)]
    store['orders'].append(order)

    # Notify User order is being processed
    update.effective_message.edit_text(text = "Your order is being processed by the store owner, just relax for awhile", reply_markup = None)

    # Notify Store Owner
    context.bot.sendMessage(chat_id = stores.ID(order.restaurant), text = "You have just received an order, click 'View Orders' to see your orders")

    # Clear bot data and user cache
    del context.bot_data[context.user_data["chat_id"]]
    context.user_data.clear()

    return ConversationHandler.END

def Cancel(update, context):
    # Ends conversation right away
    context.bot.sendMessage(chat_id = update.effective_chat.id, text = "See you next time!")

    context.user_data.clear()
    return ConversationHandler.END

def addPreOrderHandlersTo(dispatcher):
    # Build handlers
    start_conv = ConversationHandler(entry_points = [CommandHandler("LetsMakan", LetsMakan)], states = {
        sub_1 : [CallbackQueryHandler(LetsMakan_helper)]
    }, fallbacks = [CommandHandler("cancel", Cancel)], per_user = True, per_chat= False)

    end_conv = ConversationHandler(entry_points = [CommandHandler("EndMakan", EndMakan)], states = {
        sub_1 : [MessageHandler(Filters.regex('^Confirm plus chop$')|Filters.regex('^Hol up$'), EndMakan_helper)],
        sub_2 : [MessageHandler(Filters.regex('^[0-9]*$'), save_phone)],
        sub_3 : [CallbackQueryHandler(save_address)],
    }, fallbacks = [CommandHandler("cancel", Cancel)], per_user = True, per_chat= False)
    
    # Add to dispatcher
    dispatcher.add_handler(CommandHandler('poll', poll))
    dispatcher.add_handler(PollAnswerHandler(receive_poll_answer))
    dispatcher.add_handler(start_conv)
    dispatcher.add_handler(end_conv)
    dispatcher.add_handler(CommandHandler("cancelmakan", CancelMakan))

def messageError(update, context, chat_type = "group"):
    # Check where the message is coming from
    error = update.effective_message.chat.type != chat_type
    if(error):
        context.bot.sendMessage(update.effective_user.id, text = "Please send your commands in a group!")
    elif not update.effective_chat.id in context.bot_data:
        error = True
        context.bot.sendMessage(update.effective_chat.id, text = "Please create a makan session first!")
    return error


def poll(update, context):
    """Sends a predefined poll"""
    # Check for available restaurants
    available_restaurants = []
    for id in stores.toList("ID"):
        if context.bot_data[id]['Store Open']:
            available_restaurants.append(stores.stores(id))

    
    if not available_restaurants:
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Sorry, there are not restaurants available at this time")
        return ConversationHandler.END
    elif len(available_restaurants)== 1:
        context.bot.sendMessage(chat_id = update.effective_chat.id, text = "Only {} is available. Select /LetsMakan to start ordering!".format(available_restaurants[0]))
    else:
        questions = available_restaurants
        message = context.bot.send_poll(update.effective_chat.id, "Please vote for a store", questions,
                                    is_anonymous=False)

        # Save some info about the poll the bot_data for later use in receive_poll_answer
        context.bot_data["poll"][message.poll.id] = {"questions": questions, "message_id": message.message_id,
                                    "chat_id": update.effective_chat.id, "answers": 0, 
                                    "limit": update.effective_chat.get_members_count()-1}

def receive_poll_answer(update, context):
    """Summarize a users poll vote"""
    answer = update.poll_answer
    poll_id = answer.poll_id
    try:
        questions = context.bot_data["poll"][poll_id]["questions"]
    # this means this poll answer update is from an old poll, we can't do our answering then
    except KeyError:
        return
    selected_options = answer.option_ids
    answer_string = ""
    for question_id in selected_options:
        if question_id != selected_options[-1]:
            answer_string += questions[question_id] + " and "
        else:
            answer_string += questions[question_id]
    user_mention = mention_html(update.effective_user.id, update.effective_user.full_name)

    # save results
    context.bot.send_message(context.bot_data["poll"][poll_id]["chat_id"],
                             "{} chose {}!".format(user_mention, answer_string),
                             parse_mode=ParseMode.HTML)
    context.bot_data["poll"][poll_id]["answers"] += 1
    # Close poll after three participants voted
    if context.bot_data["poll"][poll_id]["answers"] == context.bot_data["poll"][poll_id]["limit"]:
        context.bot.sendMessage(context.bot_data["poll"][poll_id]["chat_id"], text = "Poll Closed! Please select /LetsMakan to start ordering!")
        context.bot.stop_poll(context.bot_data["poll"][poll_id]["chat_id"],
                              context.bot_data["poll"][poll_id]["message_id"])
