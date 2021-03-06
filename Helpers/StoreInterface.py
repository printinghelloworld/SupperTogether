from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, CallbackContext, PicklePersistence
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from multiprocessing import Queue
from Helpers.Data import menu, stores
from multiprocessing import Manager
import logging

#Loggin
logging.basicConfig(format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level = logging.INFO)

CHOOSING, VIEWING_SPECIFIC_ORDER, AFTER_VIEWING_ORDER, AFTER_VIEWING_COMPLETED_ORDER, POST_REJECTION, ACCEPTED, CONFIRMING_STAGE, CHOOSING_CAT, BLOCKING, REDIRECT = range(10)

default_keyboard = [['Close Shop'],
            ['View Orders'],
            ['View Completed Orders'],
            ['Block Orders']
            ]

def build_menu(buttons,
            n_cols,	
            header_buttons = None,
            footer_buttons = None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, [header_buttons])
    if footer_buttons:
        menu.append([footer_buttons])
    return menu

def InlineKeyboard(list_of_options):
    keyboard = [InlineKeyboardButton(item, callback_data = item) for item in list_of_options]
    return InlineKeyboardMarkup(build_menu(keyboard, n_cols = 1))

def displayOrdersKeyboard(list_of_customerData):
    keyboard = [InlineKeyboardButton(item.split("_")[0], callback_data = item.split("_")[1]) for item in list_of_customerData]
    return InlineKeyboardMarkup(build_menu(keyboard, n_cols = 1))


def defaultMenu(update, context):

    # remove previous message (if any)
    if hasattr(update.callback_query, 'message'): 
        context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    bot_data = context.bot_data
    storeID = update.effective_user.id

    # Authentication process
    listOfStoreIDs = stores.list_of_ids
    if storeID in listOfStoreIDs:
        # check if Shop status is Open
        if bot_data[storeID]["Store Open"]:
            # clear chosen order data (if there's any)
            context.user_data.pop("order", None)
            # reset completed boolean to false 
            context.user_data["Completed"] = False

            # display the menu options 
            markup = ReplyKeyboardMarkup(default_keyboard, one_time_keyboard=True)

            context.bot.sendMessage(chat_id = update.effective_user.id, text = "Choose an Action:", reply_markup = markup)

            return CHOOSING
        else: 
            update.message.reply_text("Your store is not open! Use /open to start receiving orders.")            
    else:
        update.message.reply_text("You do not have access to this command. Use /help to see the list of commands available.")
    
    return ConversationHandler.END

def closeStore(update, context):

    bot_data = context.bot_data
    storeID = update.effective_user.id

    # clear chosen order data (if there's any)
    context.user_data.pop("order", None)
    context.user_data.pop("completedOrders", None)

    listOfOrders = context.bot_data[storeID]["orders"]

    numPendingOrders = sum(order.accepted == None for order in listOfOrders)

    if any(order.accepted for order in listOfOrders):
        # case where owner still has accepted orders
        update.message.reply_text("You still have accepted orders waiting to be served. Please reject the orders before closing your store.")
    elif any(order.accepted == None for order in listOfOrders):
        # case where owner still has pending orders
        update.message.reply_text("You still have {} pending orders. Please reject the orders before closing your store.".format(numPendingOrders))
    else :
        bot_data[storeID]["Store Open"] = False
        update.message.reply_text("You will stop receiving orders. Have a good rest!")
        
    return ConversationHandler.END

def openStore(update, context):
    
    bot_data = context.bot_data
    storeID = update.effective_user.id

    # Authentication process
    listOfStoreIDs = stores.list_of_ids
    if storeID in listOfStoreIDs:
        if bot_data[storeID]["Store Open"]:
            update.message.reply_text("Your store is already open! Use /menu to access the main menu.")
        else:    
            # initialize completed order list
            context.user_data["completedOrders"] = []
            context.user_data["Completed"] = False

            bot_data[storeID]["Store Open"] = True
            markup = ReplyKeyboardMarkup(default_keyboard, one_time_keyboard=True)
            update.message.reply_text("You will start receiving orders. \n We will notify you when there's a new order.", reply_markup = markup)
            return CHOOSING
    else:
        update.message.reply_text("You do not have access to this command. Use /help to see the list of commands available.")
        
    return ConversationHandler.END


def accepting(update, context):
    # remove 'Choose an order'
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    keyboard = ["30 mins", "1 hour", "1.5 hours", "2 hours", "Back"]
    reply_markup = InlineKeyboard(keyboard)
    context.bot.sendMessage(chat_id = update.effective_user.id, text = "Estimated Waiting Time: ", reply_markup = reply_markup)

    return CONFIRMING_STAGE

def deleting(update, context):
    # remove previous message
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    storeID = update.effective_chat.id
    # remove order from List
    orderList = context.bot_data[storeID]["orders"]

    # find specific order in orderList and delete that order
    currentOrder = context.user_data["order"]

    newList = Manager().list()
    for order in orderList:
        if order.user.id == currentOrder.user.id:
            continue
        newList.append(order)
    
    context.bot_data[storeID]["orders"] = newList

    reply_keyboard = [['Done']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    context.bot.sendMessage(chat_id = update.effective_user.id, text = "The order has been deleted.", reply_markup = markup)

    return ACCEPTED

def rejecting(update, context):
    # remove 'choose an action'
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    keyboard = ["Reject", "Back"]

    reply_markup = InlineKeyboard(keyboard)
    context.bot.sendMessage(chat_id = update.effective_user.id, text = "Do you really want to reject this order? This action is irreversible!", reply_markup = reply_markup)
    return CONFIRMING_STAGE

def completing(update, context):
    # remove 'choose an action'
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)
    
    storeID = update.effective_user.id
    
    keyboard = ["Yes", "Back"]

    # Display list of items ordered before confirming 
    order = context.user_data["order"]
    newDict = generateNewDict(order.food)
    itemsOrderedInTextForm = generateFoodList(newDict, storeID)

    reply_markup = InlineKeyboard(keyboard)
    context.bot.sendMessage(chat_id = update.effective_user.id, text = itemsOrderedInTextForm + "\n" + "Are you sure the order has been completed and is ready to be delivered?", reply_markup = reply_markup)
    return CONFIRMING_STAGE


def rejected(update, context):
    # remove 'do u really want to reject this order'
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    context.bot.sendMessage(chat_id = update.effective_user.id, text = "You have rejected the order. Please input your reason for rejection this order. (ie. Closing soon, no time etc)")
    return POST_REJECTION

def send_rejection(update, context):

    reason = update.message.text
    customerID = context.user_data["order"].user.id
    storeID = update.effective_user.id

    # send Message to customer
    context.bot.sendMessage(chat_id = customerID, text = "Sorry, your order has been rejected. Reason: {}".format(reason))

    # set Accepted boolean of Order in Queue to False
    orderList = context.bot_data[storeID]["orders"]

    newList = Manager().list()

    # find specific order in orderList
    order = context.user_data["order"]
    for item in orderList:
        if item.user.first_name == order.user.first_name and item.user.id == order.user.id:
            item.accepted = False
        
        newList.append(item)

    # assign tempQueue as the queue in orders so the data will not be lost
    context.bot_data[storeID]["orders"] = newList

    reply_keyboard = [['Done']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    update.message.reply_text("We will inform the customer that their order has been rejected. Have a nice day!", reply_markup = markup)
    return ACCEPTED

def accepted(update, context):
    # remove' estimated waiting time'
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    timeChosen = update.callback_query.data

    customerID = context.user_data["order"].user.id

    storeID = update.effective_user.id
    
    context.bot.sendMessage(chat_id = customerID, text = "Your order has been accepted! Estimated Waiting Time: {}".format(timeChosen))

    # change Accepted boolean of the order to True
    orderList = context.bot_data[storeID]["orders"]
    newList = Manager().list()

    # find specific order in orderList
    order = context.user_data["order"]
    for item in orderList:
        if item.user.first_name == order.user.first_name and item.user.id == order.user.id:
            item.accepted = True
        
        newList.append(item)

    # assign tempQueue as the queue in orders so the data will not be lost
    context.bot_data[storeID]["orders"] = newList

    reply_keyboard = [['Done']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    context.bot.sendMessage(chat_id = update.effective_user.id, reply_markup = markup, text ="You have selected {} as the estimated waiting time. Remember to select 'Deliver Order' when you're done. Happy Cooking!".format(timeChosen))

    return ACCEPTED

def completed(update, context):
    # remove 'do u really want to reject this order'
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    currentOrder = context.user_data["order"]

    # inform the customer that their order is on the way
    customerID = currentOrder.user.id
    context.bot.sendMessage(chat_id = customerID, text = "Your order is on the way! You can start making your way to the pickup location that you've provided.")

    # create a text message so owner can forward to the person doing the delivery
    storeID = update.effective_user.id
    orderInText = generateTextOrder(currentOrder, storeID)

    context.bot.sendMessage(chat_id = update.effective_user.id, text = orderInText)
    context.bot.sendMessage(chat_id = update.effective_user.id, text ="We have notified the customer that their order is on the way. You can forward the order details above to the person doing the delivery. \n Use /menu to access the Main Menu when you're done.")

    # remove order from user_data and bot_data
    context.user_data["completedOrders"].append(currentOrder)

    orderList = context.bot_data[storeID]["orders"]

    newList = Manager().list()

    for order in orderList:
        if order.user.id == currentOrder.user.id:
            continue
        newList.append(order)
    
    context.bot_data[storeID]["orders"] = newList

    context.user_data.pop("order", None)

    return ConversationHandler.END

def block_orders(update, context):
    #  # remove Previous Message
    # if hasattr(update.callback_query, 'message'): 
    #     context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    storeID = update.effective_user.id
    myStoreName = stores.stores(storeID)

    # generate category
    list_of_categories = menu.show_cat(myStoreName)

    # Create reply_markup
    buttons = [[InlineKeyboardButton(c, callback_data= c)] for c in list_of_categories]
    reply_markup = InlineKeyboardMarkup(buttons)

    # Send Message: Prompt user to select cat.
    context.bot.sendMessage(chat_id = update.effective_user.id,
                                text = "Please a category:\nPress /Cancel to cancel request", reply_markup = reply_markup)

    return CHOOSING_CAT

def checkBlockStatus(res, id):
    if menu.check_avail(res, id):
        return ""
    else:
        return " (Blocked)"

def choosing_item(update, context):
    # update.callback_query.answer()
    catSelected =  update.callback_query.data
    storeID = update.effective_user.id
    myStoreName = stores.stores(storeID)

    ID_list = menu.cat_subset_all(myStoreName, catSelected)
    Item_list = menu.list_of_items(myStoreName, ID_list)

    buttons = [[InlineKeyboardButton(Item_list[i] + checkBlockStatus(myStoreName, ID_list[i]), callback_data= ID_list[i])] for i in range(len(ID_list))]

    reply_markup = InlineKeyboardMarkup(buttons)

    update.effective_message.edit_text(text = "Select the food/drink that you want to block/unblock:\nPress /Cancel to cancel request", reply_markup = reply_markup)

    return BLOCKING

def block_item(update, context):
    itemSelected = int(update.callback_query.data)

    storeID = update.effective_user.id
    myStoreName = stores.stores(storeID)
    Item_list = menu.list_of_items(myStoreName)

    temp = 0

    if (menu.check_avail(myStoreName, itemSelected)):
        menu.block_order(myStoreName, itemSelected)
    else:
        menu.unblock_order(myStoreName, itemSelected)
        temp = 1

    keyboard = ["Done"]
    reply_markup = InlineKeyboard(keyboard)

    update.effective_message.edit_text(text = "{} has been {}".format(Item_list[itemSelected], "blocked" if temp == 0 else "unblocked"), reply_markup = reply_markup)

    return REDIRECT

def view_orders(update, context):
    # remove 'Choose an Action'
    if hasattr(update.callback_query, 'message'): 
        context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    bot_data = context.bot_data
    storeID = update.effective_user.id
    orderList = bot_data[storeID]["orders"]

    # create another list that contains the CustomerName and CustomerID
    newList = []
    for order in orderList:
        newList.append(order.user.first_name + orderStatus(order) + "_" + str(order.user.id))

    # add back button to the menu
    newList.append("Back_Back2")
    
    if len(newList) == 1:
        context.bot.sendMessage(chat_id = update.effective_user.id, text = "There are no orders at the moment. \n Click /menu to return to the Main Menu.")
        return ConversationHandler.END
    else:
        # generate menu based on Customer Name with Customer ID as its value
        markup = displayOrdersKeyboard(newList)

        context.bot.sendMessage(chat_id = update.effective_user.id, text = "Choose an order:", reply_markup = markup)
        return VIEWING_SPECIFIC_ORDER

def view_completed_orders(update, context):

    if hasattr(update.callback_query, 'message'): 
        context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)
    
    listOfCompletedOrders = context.user_data["completedOrders"]

    # create another list that contains the CustomerName and CustomerID
    newList = []
    for order in listOfCompletedOrders:
        newList.append(order.user.first_name + " (Completed)" + "_" + str(order.user.id))

    # add back button to the menu
    newList.append("Back_Back2")

    if len(newList) == 1:
        context.bot.sendMessage(chat_id = update.effective_user.id, text = "There are no completed orders at the moment. \n Click /menu to return to the Main Menu.")
        return ConversationHandler.END
    else:
        # generate menu based on Customer Name with Customer ID as its value
        markup = displayOrdersKeyboard(newList)

        # set Boolean Completed to True
        context.user_data["Completed"] = True

        context.bot.sendMessage(chat_id = update.effective_user.id, text = "Choose an order:", reply_markup = markup)
        return VIEWING_SPECIFIC_ORDER

def orderStatus(order):
    if order.accepted:
        return " (Accepted)"
    elif order.accepted == None:
        return ""
    else:
        return " (Rejected)"
    
def specific_order(update, context):
    query = update.callback_query.data

    # delete previous message
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    if query != "Back":
        customerID = int(query)
        # find and save order in user_data
        print("finding order in specific order")
        # find order based on Customer ID
        orderObj = None
        storeID = update.effective_user.id
        orders = None
        if context.user_data["Completed"]:
            print("in completed scenario")
            # case where I'm viewing completed orders
            orders = context.user_data["completedOrders"]
            for order in orders:
                if order.user.id == customerID:
                    print("order found")
                    orderObj = order
        else:
            print("in normal scenario")
            orderList = context.bot_data[storeID]["orders"]

            for order in orderList:
                if order.user.id == customerID:
                    orderObj = order
            
        # save order object in User Data
        context.user_data["order"] = orderObj
    else:
        print("Back button was clicked, no need to update user_data")
    
    # Render keys based on order status
    orderObj = context.user_data["order"]
    keyboard = []
    if context.user_data["Completed"]:
        # case where I'm viewing completed orders
        keyboard = ["Order Details", "Back"]
    elif orderObj.accepted == None:
        # haven't accept or reject order
        keyboard = ["Order Details", "Accept Order", "Reject Order", "Back"]
    elif orderObj.accepted == True:
        # have the option to cancel orders 
        keyboard = ["Order Details", "Deliver Order", "Cancel Order", "Back"]
    else:
        # order has been rejected
        keyboard = ["Order Details", "Delete Order", "Back"]

    new_reply_markup = InlineKeyboard(keyboard)
    context.bot.sendMessage(chat_id = update.effective_user.id, text = "Choose an Action:", reply_markup = new_reply_markup)
    if context.user_data["Completed"]:
        return AFTER_VIEWING_COMPLETED_ORDER
    else: 
        return AFTER_VIEWING_ORDER

def list_order(update, context):
    # remove previous message
    context.bot.deleteMessage(update.effective_chat.id, update.callback_query.message.message_id)

    order = context.user_data["order"]

    storeID = update.effective_user.id

    textForm = generateTextOrder(order, storeID)

    # Create Back button
    keyboard = [[InlineKeyboardButton("Back", callback_data="Back")]]
    new_reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.sendMessage(chat_id = update.effective_user.id, text = textForm, reply_markup = new_reply_markup)
    return VIEWING_SPECIFIC_ORDER

def generateTextOrder(order, storeID):
    foodDict = order.food

    newDict = generateNewDict(foodDict)
            
    textForm = "Address: \n{} \n\nContact: \n{} \n\n".format(order.address, order.phone)
    textForm += generateFoodList(newDict, storeID)

    return textForm

def generateNewDict(foodDict):
    # create another dictionary with just the item id and quantity
    newDict = {}
    for userOrders in foodDict.values():
        for foodID, quantity in userOrders.items():
            # check if foodID exist in newDict.
            # if exist, increment the count
            # if doesn't exist, add in the foodID with qty = 1
            if foodID in newDict:
                oldValue = newDict[foodID]
                newDict[foodID] = oldValue + quantity
            else:
                newDict[foodID] = 1

    return newDict

def generateFoodList(newDict, storeID):
    # textForm = text
    text = "Items Ordered: \n"
    # convert dict into text
    for foodID, quantity in newDict.items():
        text += menu.from_tuple_to_item(stores.stores(storeID), foodID) + ": {}".format(quantity) + "\n"

    return text


def addShopHandlersTo(dispatcher):
    # Build handlers
    order_handler = ConversationHandler(
        entry_points=[CommandHandler('open', openStore), CommandHandler('menu', defaultMenu)],
        
        states={
            CHOOSING: [MessageHandler(Filters.regex('^Close Shop$'),
                                      closeStore),
                       MessageHandler(Filters.regex('^View Orders$'),
                                      view_orders),
                        MessageHandler(Filters.regex('^View Completed Orders$'), view_completed_orders),
                        MessageHandler(Filters.regex('^Block Orders$'), block_orders)
                       ],
            VIEWING_SPECIFIC_ORDER: [CallbackQueryHandler(defaultMenu, pattern="^Back2$"), CallbackQueryHandler(specific_order)],
            AFTER_VIEWING_ORDER: [CallbackQueryHandler(list_order, pattern="Order"),
             CallbackQueryHandler(accepting, pattern="Accept"),
             CallbackQueryHandler(rejecting, pattern="Reject|Cancel"),
             CallbackQueryHandler(completing, pattern="Deliver"),
             CallbackQueryHandler(deleting, pattern="Delete"),
             CallbackQueryHandler(view_orders, pattern="Back")
            ],
            CONFIRMING_STAGE: [CallbackQueryHandler(specific_order, pattern="Back"),
            CallbackQueryHandler(rejected, pattern="Reject"), 
            CallbackQueryHandler(completed, pattern="Yes"),
            CallbackQueryHandler(accepted)
            ],
            AFTER_VIEWING_COMPLETED_ORDER: [CallbackQueryHandler(list_order, pattern = "Order"),
             CallbackQueryHandler(view_completed_orders, pattern="Back")
            ],
            POST_REJECTION:[MessageHandler(Filters.text, send_rejection)],
            ACCEPTED:[MessageHandler(Filters.regex('^Done$'), defaultMenu)],
            CHOOSING_CAT:[CallbackQueryHandler(choosing_item)],
            BLOCKING:[CallbackQueryHandler(block_item)],
            REDIRECT: [CallbackQueryHandler(defaultMenu)]
        },

        fallbacks = [CommandHandler('menu', defaultMenu), CommandHandler('open', openStore), CommandHandler('cancel', defaultMenu)]
    )
    
    # Add to dispatcher
    dispatcher.add_handler(order_handler)
