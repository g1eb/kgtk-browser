import React, { useRef, useState } from 'react'
import { alpha, makeStyles } from '@material-ui/core/styles'
import Menu from '@material-ui/core/Menu'
import MenuItem from '@material-ui/core/MenuItem'
import AppBar from '@material-ui/core/AppBar'
import Toolbar from '@material-ui/core/Toolbar'
import IconButton from '@material-ui/core/IconButton'
import Typography from '@material-ui/core/Typography'
import InputBase from '@material-ui/core/InputBase'
import SearchIcon from '@material-ui/icons/Search'
import GitHubIcon from '@material-ui/icons/GitHub'
import CircularProgress from '@material-ui/core/CircularProgress'

import Logo from './Logo'
import search from '../utils/search'


const useStyles = makeStyles(theme => ({
  header: {
    color: '#fefefe',
    marginTop: theme.spacing(0),
  },
  grow: {
    flexGrow: 1,
  },
  appBar: {
    backgroundColor: 'rgba(254, 254, 254, 0.25)',
    marginBottom: theme.spacing(1),
    padding: theme.spacing(0),
  },
  menuIcon: {
    width: theme.spacing(8),
    height: theme.spacing(8),
    marginRight: theme.spacing(2),
  },
  title: {
    display: 'none',
    [theme.breakpoints.up('sm')]: {
      display: 'block',
    },
  },
  search: {
    position: 'relative',
    borderRadius: 0,
    backgroundColor: alpha(theme.palette.common.white, 0.15),
    '&:hover': {
      backgroundColor: alpha(theme.palette.common.white, 0.25),
    },
    marginRight: theme.spacing(2),
    marginLeft: 0,
    width: '100%',
    [theme.breakpoints.up('sm')]: {
      marginLeft: theme.spacing(3),
      minWidth: '350px',
      width: 'auto',
    },
  },
  searchIcon: {
    padding: theme.spacing(0, 2),
    height: '100%',
    position: 'absolute',
    pointerEvents: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingIcon: {
    top: theme.spacing(1.2),
    right: theme.spacing(2),
    position: 'absolute',
    pointerEvents: 'none',
    '& .MuiCircularProgress-root': {
      color: '#fefefe',
    },
  },
  inputRoot: {
    color: 'inherit',
  },
  inputInput: {
    padding: theme.spacing(1, 1, 1, 0),
    // vertical padding + font size from searchIcon
    paddingLeft: `calc(1em + ${theme.spacing(4)}px)`,
    transition: theme.transitions.create('width'),
    width: '100%',
    [theme.breakpoints.up('md')]: {
      width: '20ch',
    },
  },
  menu: {
    '& .MuiMenu-paper': {
      borderRadius: 0,
      padding: 0,
      '& > ul': {
        padding: 0,
        minWidth: '350px',
        maxWidth: '500px',
        maxHeight: '300px',
        overflowY: 'auto',
      },
    },
  },
  menuItem: {
    '& > p': {
      width: '100%',
      overflow: 'hidden',
      whiteSpace: 'nowrap',
      textOverflow: 'ellipsis',
    },
  },
  sectionDesktop: {
    display: 'none',
    [theme.breakpoints.up('md')]: {
      display: 'flex',
    },
  },
}))


const Header = ({ getData }) => {

  const classes = useStyles()

  const timeoutID = useRef(null)

  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [anchorElement, setAnchorElement] = useState()

  const closeMenu = () => {
    setAnchorElement()
  }

  const selectResult = item => {
    setAnchorElement()
    getData(item.ref)
  }

  const handleOnChange = event => {
    const value = event.target.value
    clearTimeout(timeoutID.current)
    timeoutID.current = setTimeout(() => {
      if ( !value ) {
        setResults([])
        closeMenu()
      } else if (value.length > 1)  {
        setLoading(true)
        search(value).then(results => {
          if ( !!results.length ) {
            setAnchorElement(event.target)
            setResults(results.slice(0, 10)) // Limit the results to 10 values.
          }
          setLoading(false)
        })
      }
    }, 500)
  }

  const handleOnKeyUp = event => {
    const value = event.target.value
    if (event.key === 'Enter') {
      if ( !!results.length ) {
        const item = results[0]
        setResults([])
        closeMenu()
        selectResult(item)
      } else if (value.length > 0) {
        setResults([])
        closeMenu()
        setAnchorElement()
        getData(value)
      }
    }
  }

  const renderSearchResults = () => {
    return (
      <Menu
        keepMounted
        id="search-results"
        className={classes.menu}
        anchorEl={anchorElement}
        autoFocus={false}
        disableAutoFocus={true}
        disableEnforceFocus={true}
        transformOrigin={{
          vertical: -55,
          horizontal: 0,
        }}
        open={!!anchorElement}
        onClose={closeMenu}>
        {results.map(item => (
          <MenuItem key={item.ref}
            className={classes.menuItem}
            onClick={() => selectResult(item)}>
            <Typography variant="body1">
              <b>{item.ref}</b>
              <br/>
              {item.description}
            </Typography>
          </MenuItem>
        ))}
      </Menu>
    )
  }

  return (
    <div className={classes.grow}>
      <AppBar position="static" className={classes.appBar}>
        <Toolbar>
          <div className={classes.menuIcon}>
            <Logo/>
          </div>
          <Typography className={classes.title} variant="h6" noWrap>
            KGTK Browser
          </Typography>
          <div className={classes.search}>
            <div className={classes.searchIcon}>
              <SearchIcon />
            </div>
            <InputBase
              placeholder="Search…"
              classes={{
                root: classes.inputRoot,
                input: classes.inputInput,
              }}
              inputProps={{ 'aria-label': 'search' }}
              onChange={handleOnChange}
              onKeyUp={handleOnKeyUp}
            />
            {loading && (
              <div className={classes.loadingIcon}>
                <CircularProgress size={16} />
              </div>
            )}
            {renderSearchResults()}
          </div>
          <div className={classes.grow} />
          <div className={classes.sectionDesktop}>
            <IconButton
              color="inherit"
              href="https://github.com/usc-isi-i2/kgtk"
              title="Knowledge Graph Toolkit"
              rel="noopener noreferrer nofollow"
              target="_blank">
              <GitHubIcon fontSize="large" />
            </IconButton>
          </div>
        </Toolbar>
      </AppBar>
    </div>
  )
}


export default Header
