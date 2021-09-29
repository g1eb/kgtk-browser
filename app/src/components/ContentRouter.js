import React from 'react'
import {
  Route,
  Switch,
  BrowserRouter,
} from 'react-router-dom'

import Content from './Content'
import ItemContent from './ItemContent'


const ContentRouter = () => (
	<BrowserRouter>
	  <Switch>
	    <Route exact path='/' component={Content}/>
	    <Route exact path='/browser' component={Content}/>
	    <Route path='/item/:id' component={ItemContent}/>
	    <Route path='/browser/item/:id' component={ItemContent}/>
	  </Switch>
	</BrowserRouter>
)


export default ContentRouter
